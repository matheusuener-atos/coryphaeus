/* ------------------------------------- o lancamento pela conversa (T4) */
/*
   Pacote de telas de 01/10/2026: `Conversa - Lancamento` e `Conversa -
   Recebimento` (src/lancamentos_pela_conversa.py).

   O lancamento abre na coluna da direita (420 px) ja preenchido: o valor,
   a descricao, a categoria e a forma, o cliente, o vencimento e, se ja
   aconteceu, o dia do pagamento; o anexo (boleto, comprovante) vem conferido
   com o que a pessoa disse. No recebimento, a cobranca em aberto que ele
   paga e a que se atualiza (a parcela mais os juros), e nao uma nova.

   Na conversa: os numeros do mes (saldo, a receber, a pagar, em atraso) com
   o que o lancamento muda, e a lista do mes com a linha nova marcada.
   Lancar grava pelo POST /api/financeiro/lancar-pela-conversa (baixa, papel
   e lembrete na Agenda) e a conversa registra (/fazer "lancamento").
*/

const lcn = { d: null, v: null, caixa: null, painel: null, lista: [], clientes: [], categorias: [] };
const LCN_FORMAS = [["", "—"], ["boleto", "Boleto"], ["pix", "Pix"], ["transferencia", "Transferência"], ["cartao", "Cartão"],
  ["dinheiro", "Dinheiro"], ["debito", "Débito automático"]];
const LCN_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

function lcnReais(centavos, sinal) {
  const n = Math.abs(Number(centavos) || 0) / 100;
  return (sinal ? (centavos < 0 ? "– " : "+ ") : "") + n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function lcnCurto(centavos) {
  return "R$ " + Math.round((Number(centavos) || 0) / 100).toLocaleString("pt-BR");
}

function cartaoDeLancamento() {
  return '<div class="fcn-cartao" data-lcn-cartao="1"><div class="emc-carregando">' + esqueleto("lista") + "</div></div>";
}

function ligarLancamentoNaProposta(caixa, d) {
  const alvo = caixa.querySelector("[data-lcn-cartao]");
  if (!alvo) return;
  if (caixa.dataset.propostaGuardada) {
    alvo.innerHTML = '<div class="emc-fechado">' + ic("payments", 16) + "<span>Lançamento de “" + esc(d.titulo || "valor") + "”</span>" +
      '<button type="button" class="emc-botao" data-lcn-reabrir="1">Abrir o lançamento</button></div>';
    alvo.querySelector("[data-lcn-reabrir]").onclick = () => abrirLancamentoNaConversa(alvo, d);
    return;
  }
  abrirLancamentoNaConversa(alvo, d);
}

async function abrirLancamentoNaConversa(alvo, d) {
  const c = d.campos || {};
  lcn.d = d;
  lcn.caixa = alvo;
  lcn.feito = null;
  lcn.v = {
    id: c.id || null, tipo: c.tipo || "despesa", centavos: Number(c.centavos) || 0, descricao: c.descricao || "", categoria: c.categoria || "outros",
    forma: c.forma || "", cadastro_id: c.cadastro_id || "", servico_id: c.servico_id || "", vencimento: c.vencimento || "", liquidado_em: c.liquidado_em || "",
    papel: c.papel || null, lembrar: Boolean(c.lembrar), original: Number(c.original_centavos) || 0, juros: Number(c.juros_centavos) || 0,
  };
  await carregarMesDoLancamento();
  desenharCartaoDoLancamento();
  abrirFormularioDoLancamento();
}

async function carregarMesDoLancamento() {
  const v = lcn.v;
  // O mes da lista: o do pagamento quando ja foi pago (a parcela de setembro
  // paga hoje entra no mes de hoje), senao o do vencimento.
  const mes = (v.liquidado_em || v.vencimento || new Date().toISOString()).slice(0, 7);
  lcn.mes = mes;
  try {
    const [f, l] = await Promise.all([
      fetch("/api/financeiro?mes=" + mes).then((r) => r.json()),
      fetch("/api/financeiro/lancamentos?tipo=" + v.tipo + "&mes=" + mes).then((r) => r.json()),
    ]);
    lcn.painel = f.painel || {};
    lcn.clientes = f.clientes || [];
    lcn.categorias = f.opcoes_categoria || [];
    lcn.servicos = f.servicos || [];
    lcn.lista = l.lancamentos || [];
  } catch (err) { lcn.painel = {}; lcn.lista = []; }
}

/* O que o lancamento muda nos numeros do mes, antes de gravar. */
function deltasDoLancamento() {
  const v = lcn.v;
  const d = { saldo: 0, receber: 0, pagar: 0, atraso: 0 };
  if (lcn.feito) return d;
  const pago = Boolean(v.liquidado_em);
  if (v.tipo === "recebimento") {
    if (pago) d.saldo = v.centavos;
    if (v.id) d.receber = -(v.original || v.centavos);
    else if (!pago) d.receber = v.centavos;
    const antes = lcn.lista.find((x) => x.id === v.id);
    if (antes && antes.atrasado && pago) d.atraso = -(v.original || antes.centavos);
  } else {
    if (pago) d.saldo = -v.centavos;
    else d.pagar = v.centavos;
  }
  return d;
}

/* `bomSubir`: no saldo, subir e bom; no a pagar e no atraso, e o contrario;
   no a receber, descer porque entrou dinheiro e bom. */
function kpiDoLancamento(rotulo, centavos, delta, sub, tom, bomSubir) {
  const classe = "lcn-kpi" + (tom ? " " + tom : "");
  const classeDelta = "lcn-delta" + ((delta > 0) === Boolean(bomSubir) ? " sobe" : " desce");
  return '<div class="' + classe + '"><span class="emc-kicker">' + esc(rotulo) + "</span>" +
    "<b>" + (tom === "nada" ? "nada" : lcnCurto(centavos)) + (delta ? '<small class="' + classeDelta + '">' + (delta > 0 ? "+ " : "– ") +
      Math.round(Math.abs(delta) / 100).toLocaleString("pt-BR") + "</small>" : "") + "</b><small>" + esc(sub) + "</small></div>";
}

function desenharCartaoDoLancamento() {
  const alvo = lcn.caixa;
  if (!alvo || !alvo.isConnected) return;
  const v = lcn.v;
  const p = lcn.painel || {};
  const d = deltasDoLancamento();
  const atraso = (p.atrasado || 0) + d.atraso;
  const kpis = '<div class="lcn-kpis">' +
    kpiDoLancamento("Saldo em caixa", (p.saldo || 0) + d.saldo, d.saldo, (p.resultado_mes >= 0 ? "+ " : "– ") + lcnCurto(Math.abs(p.resultado_mes || 0)) + " no mês", "", true) +
    kpiDoLancamento("A receber", (p.a_receber || 0) + d.receber, d.receber, plural((p.a_receber_quantos || 0) + (d.receber < 0 ? -1 : d.receber > 0 ? 1 : 0), "cobrança aberta", "cobranças abertas"), "", d.receber > 0) +
    kpiDoLancamento("A pagar", (p.a_pagar || 0) + d.pagar, d.pagar, plural((p.a_pagar_quantos || 0) + (d.pagar > 0 ? 1 : 0), "conta") + (d.pagar > 0 ? " · 1 nova" : ""), "", false) +
    kpiDoLancamento("Em atraso", atraso, d.atraso, atraso ? plural((p.atrasado_quantos || 0) + (d.atraso ? -1 : 0), "cobrança vencida", "cobranças vencidas") : "nenhuma cobrança vencida", atraso ? "" : "nada", false) +
    "</div>";
  const receber = v.tipo === "recebimento";
  const mes = LCN_MESES[Number(lcn.mes.slice(5, 7)) - 1] || "";
  let linhas = lcn.lista.slice();
  const nova = { id: v.id || "novo", vencimento: v.vencimento, descricao: v.descricao, cadastro_nome: (lcn.clientes.find((c) => String(c.id) === String(v.cadastro_id)) || {}).nome || "",
    categoria_rotulo: (lcn.categorias.find((c) => c.valor === v.categoria) || {}).rotulo || "", centavos: v.centavos, liquidado_em: v.liquidado_em, nova: !lcn.feito };
  if (v.id && linhas.some((x) => x.id === v.id)) linhas = linhas.map((x) => (x.id === v.id ? Object.assign({}, x, nova) : x));
  else if (!lcn.feito || v.id) linhas.push(nova);
  linhas.sort((a, b) => String(a.vencimento || "9").localeCompare(String(b.vencimento || "9")));
  const mostrar = linhas.slice(0, 7);
  const selo = (x) => {
    if (x.nova && !x.liquidado_em) return ["novo", "novo"];
    if (x.liquidado_em) return [receber ? "recebido" : "pago", x.nova ? "novo" : "ok"];
    return [receber ? "a receber" : "a pagar", receber ? "ok-claro" : "acc"];
  };
  const total = linhas.reduce((s, x) => s + (Number(x.centavos) || 0), 0);
  alvo.innerHTML = '<div class="fcn-tabela lcn-tabela">' + kpis +
    '<div class="fcn-tabela-cabeca"><b>' + (receber ? "A receber em " : "A pagar em ") + esc(mes) + "</b><span class=\"vazio-flex\"></span><small>" +
    (lcn.feito ? "" : "o novo lançamento aparece marcado") + "</small></div>" +
    '<div class="fcn-linha lcn-linha fcn-titulos"><span>Vence</span><span>Quem · descrição</span><span>Categoria</span><span class="fcn-num">Valor</span><span>Situação</span></div>' +
    mostrar.map((x) => {
      const s = selo(x);
      return '<div class="fcn-linha lcn-linha' + (x.nova ? " nova" : "") + '"><span class="fcn-mono">' + esc(x.vencimento ? dataCurta(x.vencimento) : "—") + "</span>" +
        '<span class="fcn-quem"><span><b>' + esc(x.cadastro_nome || x.descricao || "—") + "</b><small>" + esc(x.cadastro_nome ? x.descricao : "") + "</small></span></span>" +
        "<span>" + esc(x.categoria_rotulo || "—") + "</span>" +
        '<span class="fcn-num">' + lcnReais(receber ? x.centavos : -x.centavos, true) + "</span>" +
        '<span><span class="fcn-selo ' + s[1] + '">' + esc(s[0]) + "</span></span></div>";
    }).join("") +
    '<div class="fcn-tabela-pe"><small>' + mostrar.length + " de " + plural(linhas.length, receber ? "cobrança" : "conta") + " · ordenado por vencimento</small>" +
    '<span class="vazio-flex"></span><small>' + (receber ? "Entradas " : "Saídas ") + '<b class="fcn-num">' + lcnReais(receber ? total : -total, true) + "</b></small></div></div>";
}

/* --------------------------------------------- o lancamento, na coluna */

function htmlDoLancamento() {
  const v = lcn.v;
  const receber = v.tipo === "recebimento";
  const papel = v.papel;
  const confere = (() => {
    if (v.juros && v.original) return ["ok", "parcela " + lcnReais(v.original).replace(/^/, "R$ ") + " + juros R$ " + lcnReais(v.juros) + (papel ? " · confere com o comprovante" : "")];
    if (papel && papel.centavos) {
      return papel.centavos === v.centavos ? ["ok", "confere com o " + papel.tipo + " anexo"] : ["olhar", "o " + papel.tipo + " diz R$ " + lcnReais(papel.centavos)];
    }
    return null;
  })();
  const opcoes = (lista, atual) => lista.map(([x, r]) => '<option value="' + esc(x) + '"' + (String(x) === String(atual || "") ? " selected" : "") + ">" + esc(r) + "</option>").join("");
  const cliente = lcn.clientes.find((c) => String(c.id) === String(v.cadastro_id));
  const servicosDoCliente = v.cadastro_id ? (lcn.servicos || []).filter((s) => String(s.cadastro_id) === String(v.cadastro_id)) : [];
  // Um serviço só do cliente: já vem escolhido (a pessoa troca para "nenhum").
  if (servicosDoCliente.length === 1 && v.servico_id === "" && !v.servicoMexido) v.servico_id = String(servicosDoCliente[0].id);
  if (v.servico_id && !servicosDoCliente.some((s) => String(s.id) === String(v.servico_id))) v.servico_id = "";
  const categorias = (lcn.categorias || []).map((c) => [c.valor, c.rotulo]);
  const classeValor = "lcn-valor " + (receber ? "entra" : "sai");
  return '<div class="fcn" data-fl-tipo="lancamento">' +
    '<div class="fcn-topo"><span><b>Novo lançamento</b><small>' + (v.id ? "atualiza a cobrança que já estava aberta" : "entra na soma assim que for salvo") + "</small></span></div>" +
    '<span class="visoes fcn-abas"><button type="button" data-lcn-tipo="recebimento"' + (receber ? ' class="ativa"' : "") + ">" + ic("arrow_downward", 15) + "Recebimento</button>" +
    '<button type="button" data-lcn-tipo="despesa"' + (!receber ? ' class="ativa"' : "") + ">" + ic("arrow_upward", 15) + "Despesa</button></span>" +
    '<div class="fcn-corpo">' +
    '<div class="fcn-caixa lcn-caixa-valor"><span class="fcn-rotulo">Valor</span><label class="' + classeValor + '"><small>R$</small>' +
    '<input type="text" data-lcn="valor" value="' + esc(lcnReais(v.centavos)) + '" inputmode="decimal" aria-label="Valor"></label>' +
    (confere ? '<span class="lcn-confere ' + confere[0] + '">' + ic(confere[0] === "ok" ? "check_circle" : "error", 15) + esc(confere[1]) + "</span>" : "") + "</div>" +
    '<label class="fcn-campo"><span class="fcn-rotulo">Descrição</span><input type="text" data-lcn="descricao" value="' + esc(v.descricao) + '"></label>' +
    '<div class="fcn-par"><label class="fcn-campo meia"><span class="fcn-rotulo">Categoria</span><select data-lcn="categoria">' + opcoes(categorias, v.categoria) + "</select></label>" +
    '<label class="fcn-campo meia"><span class="fcn-rotulo">Forma</span><select data-lcn="forma">' + opcoes(LCN_FORMAS, v.forma) + "</select></label></div>" +
    '<label class="fcn-campo"><span class="fcn-rotulo">Cliente</span><select data-lcn="cadastro_id">' +
    opcoes([["", "sem cliente"]].concat(lcn.clientes.map((c) => [c.id, c.nome])), v.cadastro_id) + "</select></label>" +
    // O serviço (e o processo) do cliente escolhido: o "Cliente · processo" do desenho.
    (servicosDoCliente.length
      ? '<label class="fcn-campo"><span class="fcn-rotulo">Serviço · processo</span><select data-lcn="servico_id">' +
        opcoes([["", "nenhum"]].concat(servicosDoCliente.map((s) => [s.id, s.nome + (s.processo ? " · " + s.processo : "")])), v.servico_id) + "</select></label>"
      : "") +
    '<div class="fcn-par"><label class="fcn-campo meia"><span class="fcn-rotulo">Vencimento</span><input type="date" data-lcn="vencimento" value="' + esc(v.vencimento) + '"></label>' +
    '<label class="fcn-campo meia"><span class="fcn-rotulo">' + (receber ? "Já recebido em" : "Já pago em") + ' <i class="lcn-dica">se já aconteceu</i></span><input type="date" data-lcn="liquidado_em" value="' + esc(v.liquidado_em) + '"></label></div>' +
    (papel
      ? '<span class="fcn-rotulo">Papel</span><div class="lcn-papel">' + glifo(papel.nome) + "<span><b>" + esc(papel.nome) + "</b><small>" +
        (papel.tipo === "boleto" ? "vai para Papéis do mês · boleto" : "vai para os comprovantes do mês, no Acervo") + "</small></span>" +
        '<button type="button" class="botao-icone" data-lcn-sem-papel="1" title="Não guardar" aria-label="Não guardar o papel">' + ic("close", 16) + "</button></div>"
      : "") +
    (v.liquidado_em ? "" : '<div class="fcn-liga"><span><b>Lembrar na Agenda</b><small>um dia antes do vencimento</small></span>' +
      '<button type="button" class="interruptor-min' + (v.lembrar ? " on" : "") + '" data-lcn-lembrar="1" role="switch" aria-checked="' + v.lembrar + '" aria-label="Lembrar na Agenda"><i></i></button></div>') +
    "</div>" +
    '<div class="fcn-pe"><small class="fcn-resumo" data-lcn-resumo="1"></small><span class="dialogo-aviso" data-lcn-aviso="1"></span>' +
    '<button type="button" class="fantasma" data-lcn-nao="1">Cancelar</button>' +
    '<button type="button" class="primario" data-lcn-lancar="1">' + ic("check", 16) + "Lançar</button></div></div>";
}

function resumoDoLancamento() {
  const v = lcn.v;
  return [v.tipo === "recebimento" ? "Recebimento" : "Despesa", lcnReais(v.tipo === "recebimento" ? v.centavos : -v.centavos, true).replace(/^([+–]) /, "$1 R$ "),
    v.liquidado_em ? (v.tipo === "recebimento" ? "recebido " : "pago ") + dataCurta(v.liquidado_em) : (v.vencimento ? dataCurta(v.vencimento) : "sem data")].join(" · ");
}

function abrirFormularioDoLancamento() {
  abrirNoLado("formulario", {
    chave: "lancamento",
    html: htmlDoLancamento(),
    ligar: ligarFormularioDoLancamento,
    aoFechar: () => { lcn.v = null; atualizarPostura(); },
  });
  atualizarPostura();
}

function redesenharLancamentoNoLado() {
  const lado = $("lado-ferramenta");
  if (!lado || papelDoLado() !== "formulario" || !lcn.v) return;
  lado.innerHTML = htmlDoLancamento();
  ligarFormularioDoLancamento(lado);
}

function ligarFormularioDoLancamento(raiz) {
  const resumo = () => { const r = raiz.querySelector("[data-lcn-resumo]"); if (r) r.textContent = resumoDoLancamento(); };
  resumo();
  raiz.querySelectorAll("[data-lcn]").forEach((x) => {
    const chave = x.dataset.lcn;
    const ler = () => {
      if (chave === "valor") lcn.v.centavos = fcnCentavos(x.value);
      else lcn.v[chave] = x.value;
      if (chave === "servico_id") lcn.v.servicoMexido = true;
      resumo();
      desenharCartaoDoLancamento();
    };
    x.addEventListener("input", ler);
    x.addEventListener("change", () => { ler(); if (chave === "liquidado_em" || chave === "cadastro_id") redesenharLancamentoNoLado(); });
  });
  raiz.querySelectorAll("[data-lcn-tipo]").forEach((b) => {
    b.onclick = async () => {
      if (lcn.v.tipo === b.dataset.lcnTipo) return;
      lcn.v.tipo = b.dataset.lcnTipo;
      lcn.v.id = null;
      await carregarMesDoLancamento();
      redesenharLancamentoNoLado();
      desenharCartaoDoLancamento();
    };
  });
  const lembrar = raiz.querySelector("[data-lcn-lembrar]");
  if (lembrar) lembrar.onclick = () => { lcn.v.lembrar = !lcn.v.lembrar; redesenharLancamentoNoLado(); };
  const semPapel = raiz.querySelector("[data-lcn-sem-papel]");
  if (semPapel) semPapel.onclick = () => { lcn.v.papel = null; redesenharLancamentoNoLado(); };
  raiz.querySelector("[data-lcn-nao]").onclick = () => {
    const caixa = lcn.caixa;
    voltarAoContexto();
    if (caixa && caixa.isConnected) caixa.insertAdjacentHTML("beforeend", '<p class="explica">Tudo bem — não lancei nada.</p>');
  };
  raiz.querySelector("[data-lcn-lancar]").onclick = (e) => lancarPelaConversa(e.currentTarget);
}

async function lancarPelaConversa(botao) {
  const v = lcn.v;
  const aviso = document.querySelector("#lado-ferramenta [data-lcn-aviso]");
  const diz = (t) => { if (aviso) aviso.textContent = t; };
  if (!v.centavos) { diz("falta o valor"); return; }
  if (!String(v.descricao || "").trim()) { diz("falta a descrição"); return; }
  botao.disabled = true;
  const r = await fetch("/api/financeiro/lancar-pela-conversa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id: v.id, liquidado_em: v.liquidado_em, lembrar: Boolean(v.lembrar && !v.liquidado_em), papel: v.papel ? { nome: v.papel.nome, tipo: v.papel.tipo } : null,
      dados: { tipo: v.tipo, descricao: v.descricao.trim(), centavos: v.centavos, categoria: v.categoria, forma: v.forma,
        cadastro_id: v.cadastro_id ? Number(v.cadastro_id) : null, servico_id: v.servico_id ? Number(v.servico_id) : null, vencimento: v.vencimento },
    }),
  }).catch(() => null);
  if (!r || !r.ok) { botao.disabled = false; diz("não lancei: " + (r ? await erroDe(r) : "sem resposta")); return; }
  const d = await r.json();
  const feito = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo: "lancamento", campos: { id: d.lancamento.id, papel: d.papel, tarefa: d.tarefa } }),
  }).then((x) => (x.ok ? x.json() : null)).catch(() => null);
  lcn.feito = d.lancamento;
  lcn.v.id = d.lancamento.id;
  await carregarMesDoLancamento();
  desenharCartaoDoLancamento();
  voltarAoContexto();
  notaDeFeitoNaConversa(feito && feito.resumo ? feito.resumo + "." : "Lancei.");
}

function lancamentoAbertoNoLado() {
  return Boolean(lcn.v && papelDoLado() === "formulario" && document.querySelector("#lado-ferramenta [data-fl-tipo='lancamento']"));
}

/* Com o lancamento aberto, a frase que traz valor ou dia muda o campo. */
async function pedidoNoLancamento(pedido) {
  if (!lancamentoAbertoNoLado()) return false;
  if (/^\s*(lanc|lanç|cadastr|registr|gere|como est|abra)/i.test(pedido)) return false;
  const r = await fetch("/api/fichas/corrigir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto: pedido }) }).catch(() => null);
  const campos = r && r.ok ? (await r.json()).campos || {} : {};
  const v = lcn.v;
  const mudou = [];
  if (campos.valor) { v.centavos = fcnCentavos(campos.valor); mudou.push("o valor"); }
  if (campos.dia) {
    const base = new Date();
    const dia = new Date(base.getFullYear(), base.getMonth() + (Number(campos.dia) < base.getDate() ? 1 : 0), Number(campos.dia));
    v.vencimento = iso(dia);
    mudou.push("o vencimento");
  }
  if (!mudou.length) return false;
  $("centro").insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  notaDeFeitoNaConversa("Mudei " + mudou.join(" e ") + " no lançamento ao lado — confira e lance.");
  redesenharLancamentoNoLado();
  desenharCartaoDoLancamento();
  return true;
}
