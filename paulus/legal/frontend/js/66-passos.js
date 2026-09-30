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
