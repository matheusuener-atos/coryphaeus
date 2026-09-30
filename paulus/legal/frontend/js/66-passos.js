/* ------------------------------------------ tarefas de vários passos (L4) */
/*
   Na tela Agentes, a seção "Tarefas de vários passos": as receitas
   (contratos vencendo; revisar contra o padrão da casa), as que rodaram,
   com cada passo à vista, o relatório para abrir e "Desfazer" - o ponto de
   restauração apaga o que a tarefa criou e diz o que não pôde voltar
   (src/passos.py). Só na janela do escritório.
*/

const pas = { tipos: [], documentos: [], tarefas: [], vigia: null };

function secaoDasTarefasDePassos() {
  if (!acessoDeFora.local) return "";
  return '<section class="pas-secao"><div class="est-estantes-cabeca"><span>Tarefas de vários passos</span>' +
    '<span class="est-legenda">cada uma pode ser desfeita</span></div><div id="pas-corpo"><p class="nota">abrindo…</p></div></section>';
}

const ROTULO_ESTADO_PASSO = { esperando: "", andando: "fazendo…", feito: "feito", falhou: "falhou" };
const ROTULO_ESTADO_TAREFA = { andando: "andando", feita: "feita", falhou: "falhou", parada: "parada", desfeita: "desfeita", "desfeita em parte": "desfeita em parte" };

function cartaoDaTarefa(t) {
  const passos = t.passos.map((p) => '<li class="pas-passo ' + esc(p.estado) + '"><span>' + esc(p.titulo) + "</span><small>" +
    esc([ROTULO_ESTADO_PASSO[p.estado], p.detalhe].filter(Boolean).join(" · ")) + "</small></li>").join("");
  const r = t.resultado || {};
  const desfeito = (t.desfeita || []).map((d) => "<li>" + esc(d.titulo) + ": " + esc(d.como) + "</li>").join("");
  return '<div class="pas-tarefa" data-pas-id="' + t.id + '"><div class="pas-cab"><b>' + esc(t.nome) + "</b>" +
    '<span class="etiqueta">' + esc(ROTULO_ESTADO_TAREFA[t.estado] || t.estado) + "</span><small>" + esc(quandoCurto(t.criada_em)) + "</small></div>" +
    '<ol class="pas-passos">' + passos + "</ol>" +
    (t.erro ? '<p class="cfg-explica">' + esc(t.erro) + "</p>" : "") +
    (desfeito ? '<ul class="pas-desfeito">' + desfeito + "</ul>" : "") +
    '<div class="pas-botoes">' +
    (r.documento_id && t.estado === "feita" ? '<button data-pas-abrir="' + r.documento_id + '">' + ic("description", 16) + "Abrir o relatório</button>" : "") +
    (t.estado === "andando" ? '<button data-pas-parar="' + t.id + '">' + ic("stop", 16) + "Parar</button>" : "") +
    (["feita", "falhou", "parada"].includes(t.estado) ? '<button data-pas-desfazer="' + t.id + '">' + ic("history", 16) + "Desfazer</button>" : "") +
    "</div></div>";
}

function htmlDasTarefas() {
  const receitas = pas.tipos.map((x) => '<button class="pas-receita" data-pas-nova="' + x.id + '"><b>' + esc(x.nome) + "</b><small>" + esc(x.descricao) + "</small></button>").join("");
  return '<div class="pas-receitas">' + receitas + "</div>" +
    (pas.tarefas.length ? '<div class="pas-lista">' + pas.tarefas.slice(0, 8).map(cartaoDaTarefa).join("") + "</div>"
      : '<p class="cfg-explica">Nenhuma tarefa rodou ainda.</p>');
}

async function carregarTarefasDePassos() {
  const alvo = $("pas-corpo");
  if (!alvo) return;
  try {
    const [t, l] = await Promise.all([fetch("/api/passos/tipos").then((r) => r.json()), fetch("/api/passos").then((r) => r.json())]);
    pas.tipos = t.tipos || [];
    pas.documentos = t.documentos || [];
    pas.tarefas = l.tarefas || [];
  } catch (err) {
    alvo.innerHTML = '<p class="cfg-explica">não consegui abrir as tarefas.</p>';
    return;
  }
  desenharTarefasDePassos();
}

function desenharTarefasDePassos() {
  const alvo = $("pas-corpo");
  if (!alvo) return;
  alvo.innerHTML = htmlDasTarefas();
  alvo.querySelectorAll("[data-pas-nova]").forEach((b) => { b.onclick = () => novaTarefaDePassos(b.dataset.pasNova); });
  alvo.querySelectorAll("[data-pas-abrir]").forEach((b) => { b.onclick = () => abrirDocumento(Number(b.dataset.pasAbrir)); });
  alvo.querySelectorAll("[data-pas-parar]").forEach((b) => { b.onclick = () => fetch("/api/passos/" + b.dataset.pasParar + "/parar", { method: "POST" }).then(vigiarTarefas); });
  alvo.querySelectorAll("[data-pas-desfazer]").forEach((b) => {
    b.onclick = async () => {
      const ok = await confirmar({ titulo: "Desfazer esta tarefa?", contexto: "Tarefas de vários passos",
        texto: "O relatório que ela criou sai do editor, e os pedidos que ainda esperam em Aprovações saem da fila. O que alguém já aprovou ou mudou depois fica, e eu digo o quê.",
        confirmar: "Desfazer" });
      if (!ok) return;
      const r = await fetch("/api/passos/" + b.dataset.pasDesfazer + "/desfazer", { method: "POST" });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      const t = await r.json();
      avisoCert(t.estado === "desfeita" ? "Tarefa desfeita." : "Desfeita em parte: veja o que ficou no cartão.", { tom: "ok" });
      carregarTarefasDePassos();
    };
  });
  if (pas.tarefas.some((t) => t.estado === "andando")) vigiarTarefas();
}

function vigiarTarefas() {
  clearTimeout(pas.vigia);
  pas.vigia = setTimeout(async () => {
    if (!$("pas-corpo")) return;
    try { pas.tarefas = ((await (await fetch("/api/passos")).json()).tarefas) || []; } catch (err) { return; }
    desenharTarefasDePassos();
  }, 1200);
}

async function novaTarefaDePassos(tipo) {
  const x = pas.tipos.find((k) => k.id === tipo);
  if (!x) return;
  const opcoesDeDoc = ['<option value="">escolha…</option>'].concat(pas.documentos.map((d) => '<option value="' + esc(d) + '">' + esc(d) + "</option>")).join("");
  const campos = x.parametros.map((p) => {
    if (p.tipo === "sim_nao") {
      return '<label class="pas-sim"><input type="checkbox" data-pas-p="' + p.id + '"' + (p.padrao ? " checked" : "") + "> " + esc(p.rotulo) + "</label>";
    }
    if (p.tipo === "documento") {
      return '<div class="ag-campo"><label>' + esc(p.rotulo) + '</label><select data-pas-p="' + p.id + '">' + opcoesDeDoc + "</select></div>";
    }
    return '<div class="ag-campo"><label>' + esc(p.rotulo) + '</label><input type="number" min="1" max="3650" data-pas-p="' + p.id + '" value="' + esc(p.padrao) + '"></div>';
  }).join("");
  const lidos = {};
  x.parametros.forEach((p) => { lidos[p.id] = p.padrao; });
  const aberto = dialogo({ titulo: x.nome, contexto: "Tarefas de vários passos", html: '<p class="cfg-explica">' + esc(x.descricao) + "</p>" + campos,
    confirmar: "Rodar" });
  // O diálogo some ao confirmar: cada campo guarda o valor ao mudar.
  document.querySelectorAll("[data-pas-p]").forEach((el) => {
    const ler = () => { lidos[el.dataset.pasP] = el.type === "checkbox" ? el.checked : el.value; };
    el.addEventListener("change", ler);
    el.addEventListener("input", ler);
  });
  const r = await aberto;
  if (!r || !r.ok) return;
  const resp = await fetch("/api/passos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tipo: tipo, params: lidos }) });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  avisoCert("Tarefa começou: os passos aparecem aqui.", { tom: "ok" });
  carregarTarefasDePassos();
}

/* ------------------------------------------ pedida na conversa (N6) */
/* "Quais contratos vencem nos próximos 60 dias?" e "revise o contrato X
   contra o padrão": a regra (src/intencao.py) monta o cartão; o sim começa a
   tarefa, e o cartão mostra os passos até o relatório - ali mesmo. */

function cartaoPassos(d) {
  const c = d.campos || {};
  const revisar = c.receita === "revisar";
  const topo = '<div class="proposta-topo"><span class="' + (d.falta ? "etiqueta atencao" : "rotulo") + '">' +
    (d.falta ? "falta um dado" : "vou rodar a tarefa") + "</span><b>" + esc(d.titulo || "Tarefa de vários passos") + "</b></div>";
  const campos = revisar
    ? '<div class="linha-form"><input type="text" data-pc="documento" value="' + esc(c.documento || "") + '" placeholder="o contrato, como está no Acervo"' + (!c.documento ? " autofocus" : "") + ">" +
      '<input type="text" data-pc="padrao" value="' + esc(c.padrao || "") + '" placeholder="o padrão da casa, como está no Acervo"></div>' +
      '<label class="pas-conv-opcao"><input type="checkbox" data-pc="explicar"' + (c.explicar ? " checked" : "") + "> o assistente explica cada cláusula alterada (mais lento)</label>"
    : '<div class="linha-form"><label class="explica">nos próximos</label><input type="number" min="1" max="3650" data-pc="dias" value="' + esc(String(c.dias || 90)) + '"><span class="explica">dias</span></div>' +
      '<label class="pas-conv-opcao"><input type="checkbox" data-pc="propor"' + (c.propor ? " checked" : "") + "> propor cada data na Agenda (por Aprovações)</label>";
  const explica = revisar
    ? "Comparo cláusula por cláusula — igual, alterada, faltando, a mais — e escrevo o relatório no editor. "
    : "Pelas datas que a leitura dos documentos já conferiu, com a página e o trecho; sem modelo. O relatório vai para o editor. ";
  return '<div class="proposta">' + topo + campos +
    '<p class="explica">' + (d.falta ? "Entendi o pedido (" + esc(d.porque) + "), mas " + esc(d.falta) + ". " : "Li isso de " + esc(d.porque) + ". ") +
    explica + "A tarefa só começa com o seu sim, e dá para desfazer depois.</p>" +
    '<div class="linha-form"><button class="primario" data-prop="fazer">Rodar a tarefa</button><button data-prop="nao">Deixa pra lá</button></div></div>';
}

function acompanharPassosNaConversa(caixa, id) {
  const desenhar = (t) => {
    caixa.innerHTML = cartaoDaTarefa(t).replace('class="pas-tarefa"', 'class="pas-tarefa pas-na-conversa"');
    caixa.querySelectorAll("[data-pas-abrir]").forEach((b) => { b.onclick = () => abrirDocumento(Number(b.dataset.pasAbrir)); });
    caixa.querySelectorAll("[data-pas-parar]").forEach((b) => { b.onclick = () => fetch("/api/passos/" + id + "/parar", { method: "POST" }); });
    caixa.querySelectorAll("[data-pas-desfazer]").forEach((b) => {
      b.onclick = async () => {
        const r = await fetch("/api/passos/" + id + "/desfazer", { method: "POST" });
        if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
        desenhar(await r.json());
      };
    });
  };
  const olhar = async () => {
    if (!caixa.isConnected) return;
    let t;
    try {
      const r = await fetch("/api/passos/" + id);
      if (!r.ok) throw new Error(await erroDe(r));
      t = await r.json();
    } catch (err) { caixa.insertAdjacentHTML("beforeend", '<p class="explica">Não consegui acompanhar: ' + esc(String(err.message || err)) + "</p>"); return; }
    desenhar(t);
    if (t.estado === "andando") setTimeout(olhar, 1200);
  };
  olhar();
}
