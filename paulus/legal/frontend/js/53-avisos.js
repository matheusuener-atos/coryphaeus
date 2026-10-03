/* ------------------------------------------------------ avisos do dia */
/*
   T2 (docs/prompt-conversa-agentes-v0.md §2.7), redesenhado pelo pacote de
   telas de 01/10/2026 (docs/PLANO-TELAS-ASSISTENTE.md, T1):

     - na tela inicial, o titulo da saudacao se reveza com "Você tem novos
       avisos" (js/78-chamada-da-vez.js); o clique poe o PAINEL no lugar da
       lista de conversas: os tipos a esquerda, com a conta, a lista
       agrupada a direita (Atrasados, Conversas pela metade, Hoje, Amanha,
       Esta semana) e, no rodape, a selecao de varios. O Historico (o que ja
       foi visto) fica no fim da coluna dos tipos. Nao ha mais janela de
       "Central de avisos": o painel e o lugar deles.

   Quem junta os avisos e o servidor (src/central_avisos.py): cada aviso tem
   um id pela origem (prazo:<id>:<data>...), o que a tela de origem diria, o
   destino e as acoes diretas permitidas para quem esta usando. Aqui so se
   desenha, se marca como visto e se abre o lugar certo.

   "Visto" nao conclui nada. Concluir tarefa e marcar como pago sao outras
   acoes, com a confirmacao antes, e chamam a mesma rota da tela de origem
   (de fora, a politica dela: o que e "propor" vira pedido em Aprovacoes).

   Tem o proprio relogio, e nao um gancho em carregarAgora: a cada 5 s olha
   se a tela inicial esta a mostra, e pede ao servidor no maximo a cada 30 s
   (ou na hora, quando algo muda por aqui). Com a chave conversa.avisos
   desligada, o servidor responde {ligado: false} e nada aparece.
*/

const avs = {
  ligado: false, avisos: [], carregadoEm: 0, pedindo: false, faltou: [],
  // O painel da tela inicial: o tipo escolhido a esquerda,
  // o periodo, a busca, a lista do servidor, os grupos abertos e a selecao.
  painel: { tipo: "", periodo: "semana", termo: "", dados: null, abertos: new Set(), escolhidos: new Set(), historico: null },
  naInicio: false,
  // A faixa da tela inicial: o aviso a mostra (pelo id, para nao pular
  // quando a lista se refaz) e a posicao, para quando ele sai da lista.
  faixa: { id: "", i: 0, dir: 0 },
};
const AV_RECARGA_MS = 30000;
const AV_JSON = { "Content-Type": "application/json" };

/* Os tipos na coluna da esquerda, em quatro gavetas (pacote de telas). */
const AV_GAVETAS = [
  ["Dinheiro", ["a_pagar", "a_receber", "vencimento"]],
  ["Prazos e processos", ["prazo", "publicacao", "processo"]],
  ["Agenda", ["compromisso", "tarefa"]],
  ["Conversas", ["pendencia"]],
  ["Outros", ["conflito", "rotina"]],
];
const AV_ROTULO = {
  a_pagar: "A pagar", a_receber: "A receber", vencimento: "Vencimento", prazo: "Prazo", publicacao: "Publicação",
  processo: "Processo", compromisso: "Compromisso", tarefa: "Tarefa", pendencia: "Pendência", conflito: "Conflito", rotina: "Rotina",
};
const AV_ICONE = {
  a_pagar: "payments", a_receber: "payments", vencimento: "event", prazo: "schedule", publicacao: "description",
  processo: "folder", compromisso: "event", tarefa: "task_alt", pendencia: "forum", conflito: "group", rotina: "history",
};
// Na ordem em que aparecem na lista; "conversas pela metade" e um grupo a
// parte, logo depois dos atrasados.
const AV_GRUPOS = [
  ["atrasado", "Atrasados", "acc"], ["conversas", "Conversas pela metade", "ambar"], ["hoje", "Hoje", ""],
  ["amanha", "Amanhã", ""], ["semana", "Esta semana", ""], ["depois", "Depois", ""],
];
const AV_POR_GRUPO = 4;

function avNaInicio() {
  const c = $("conversa-col");
  return Boolean(c && c.classList.contains("vazia"));
}

async function carregarAvisosDoDia(forcar) {
  const caixa = $("av-dia");
  if (!caixa) return;
  if (!avNaInicio()) { caixa.hidden = true; return; }
  if (!forcar && avs.carregadoEm && Date.now() - avs.carregadoEm < AV_RECARGA_MS) { desenharAvisos(); return; }
  if (avs.pedindo) return;
  avs.pedindo = true;
  try {
    const r = await fetch("/api/central-avisos/hoje");
    const d = r.ok ? await r.json() : { ligado: false, avisos: [] };
    avs.ligado = Boolean(d.ligado);
    avs.avisos = d.avisos || [];
    avs.faltou = d.faltou || [];
    avs.carregadoEm = Date.now();
  } catch (err) {
    /* sem servidor agora: fica o que estava */
  } finally {
    avs.pedindo = false;
  }
  desenharAvisos();
}

function rotuloDaAcao(x) {
  return x.propoe ? "Propor: " + x.rotulo.charAt(0).toLowerCase() + x.rotulo.slice(1) : x.rotulo;
}

function iconeDoAviso(a) {
  return AV_ICONE[a.tipo] || a.icone || "notifications";
}

function ehConversaPelaMetade(a) {
  return a.tipo === "pendencia" && a.destino && a.destino.tela === "conversa";
}

/* ------------------------------------------------- a faixa na inicio */

function vemHoje(a) {
  return a.grupo === "hoje" && a.destaque && !ehConversaPelaMetade(a);
}

/* A ordem da faixa: atrasados, o que vence hoje, as conversas pela metade e
   o resto na ordem do servidor (que ja vem pela data). */
function filaDaFaixa(lista) {
  const resto = ["hoje", "amanha", "semana", "depois"];
  const peso = (a) => (a.grupo === "atrasado" ? 0 : vemHoje(a) ? 1 : ehConversaPelaMetade(a) ? 2 : 3 + Math.max(0, resto.indexOf(a.grupo)));
  return lista.map((a, i) => [a, i]).sort((x, y) => peso(x[0]) - peso(y[0]) || x[1] - y[1]).map((x) => x[0]);
}

/* "e mais 3 atrasados, 20 conversas pela metade": o que mais pede a mesma
   atencao, sem contar o aviso que esta a mostra. */
function restoDaFaixa(lista, atual) {
  const conta = (f) => lista.filter((a) => a !== atual && f(a)).length;
  const partes = [];
  const atrasados = conta((a) => a.grupo === "atrasado");
  const hoje = conta(vemHoje);
  const metade = conta(ehConversaPelaMetade);
  if (atrasados) partes.push(atrasados + (atrasados === 1 ? " atrasado" : " atrasados"));
  if (hoje) partes.push(hoje + (hoje === 1 ? " vence hoje" : " vencem hoje"));
  if (metade) partes.push(metade + (metade === 1 ? " conversa pela metade" : " conversas pela metade"));
  return partes.length ? "e mais " + partes.join(", ") : "";
}

function tomDoAviso(a) {
  return a.grupo === "atrasado" ? "atrasado" : ehConversaPelaMetade(a) ? "metade" : "";
}

/* Enquanto houver aviso, o item Aprovacoes do trilho pisca (ate os avisos
   morarem la). */
function piscarAprovacoes() {
  const pisca = Boolean(avs.ligado && (avs.avisos || []).length);
  document.querySelectorAll('[data-destino="aprovacoes"]').forEach((b) => b.classList.toggle("pisca-avisos", pisca));
}

function desenharAvisos() {
  const caixa = $("av-dia");
  if (!caixa) return;
  const lista = avs.avisos || [];
  // Vazio: sem avisos (ou com a chave desligada) a faixa nao aparece; com o
  // painel aberto no lugar da lista, ela sai (e o mesmo assunto).
  piscarAprovacoes();
  if (!avs.ligado || !lista.length || !avNaInicio() || avs.naInicio) {
    caixa.hidden = true;
    caixa.innerHTML = "";
    delete caixa.dataset.assinatura;
    // O painel se desenha uma vez; depois ele mesmo se refaz (recarregar).
    if (avs.naInicio && avNaInicio() && !document.querySelector("#av-painel [data-av-painel]")) desenharPainelNaInicio();
    if (typeof atualizarChamadaDaVez === "function") atualizarChamadaDaVez();
    return;
  }
  // Sem faixa propria: a vez dos avisos e a chamada da tela inicial
  // (js/78-chamada-da-vez.js), com "Ver agora" e "Outra hora".
  caixa.hidden = true;
  if (typeof atualizarChamadaDaVez === "function") atualizarChamadaDaVez();
}

function avisoPorId(id, lista) {
  return (lista || avs.avisos || []).find((a) => a.id === id) ||
    ((avs.painel.dados && avs.painel.dados.avisos) || []).find((a) => a.id === id) ||
    (avs.avisos || []).find((a) => a.id === id) || null;
}

/* Os botoes de uma linha (visto, abrir, a acao direta) e o clique na linha. */
function ligarLinhasDeAviso(raiz, lista) {
  raiz.querySelectorAll("[data-av-visto]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); marcarAvisoVisto(b.dataset.avVisto, b); };
  });
  raiz.querySelectorAll("[data-av-desmarcar]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); desmarcarAviso(b.dataset.avDesmarcar); };
  });
  raiz.querySelectorAll("[data-av-abrir]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); const a = avisoPorId(b.dataset.avAbrir, lista()); if (a) abrirAviso(a); };
  });
  raiz.querySelectorAll("[data-av-acao]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); const a = avisoPorId(b.dataset.avAcao, lista()); if (a) fazerAcaoDoAviso(a, Number(b.dataset.avI)); };
  });
}

/* ---------------------------------------------------- marcar como visto */

async function marcarAvisoVisto(id, botao) {
  if (botao) botao.disabled = true;
  let r;
  try {
    r = await fetch("/api/central-avisos/visto", { method: "POST", headers: AV_JSON, body: JSON.stringify({ id: id }) });
  } catch (err) {
    if (botao) botao.disabled = false;
    avisoCert("não consegui marcar agora — o programa respondeu?", { tom: "erro" });
    return false;
  }
  if (!r.ok) {
    if (botao) botao.disabled = false;
    avisoCert(await erroDe(r), { tom: "erro" });
    carregarAvisosDoDia(true);
    return false;
  }
  const d = await r.json();
  if (botao) botao.innerHTML = '<span class="ic ic-18 ag-feita-ic">check_circle</span>';
  const linha = botao ? botao.closest(".avp-linha") : null;
  const depois = () => {
    avs.avisos = d.avisos || [];
    avs.carregadoEm = Date.now();
    desenharAvisos();
    if (painelDeAvisosAberto()) recarregarPainelDeAvisos();
  };
  // Marcada, a linha sai com uma animacao curta; com as animacoes
  // reduzidas, sai na hora.
  if (linha && animacoesLigadas()) {
    linha.classList.add("av-saindo");
    setTimeout(depois, 240);
  } else {
    depois();
  }
  avisoCert("marcado como visto — está no Histórico dos avisos", {
    tom: "ok", acao: { rotulo: "Desfazer", fazer: () => desmarcarAviso(id) },
  });
  return true;
}

async function desmarcarAviso(id) {
  const r = await fetch("/api/central-avisos/desmarcar", { method: "POST", headers: AV_JSON, body: JSON.stringify({ id: id }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  avs.avisos = d.avisos || [];
  avs.carregadoEm = Date.now();
  desenharAvisos();
  if (painelDeAvisosAberto()) recarregarPainelDeAvisos();
  avisoCert("desmarcado — o aviso voltou para a tela inicial", { tom: "ok" });
}

/* ------------------------------------------------------- abrir e agir */

async function abrirAviso(a) {
  const d = a.destino || {};
  if (d.tela === "tarefa") { marcarDestino("calendario"); abrirTarefaNaAgenda(d.id, d.data, false); return; }
  if (d.tela === "compromisso") {
    // A semana do compromisso, e a ficha dele aberta - como pela grade.
    ag.dia = d.data;
    ag.semana = iso(segundaDe(deIso(d.data)));
    await mostrarAgenda("semana");
    const c = ((ag.grade && ag.grade.compromissos) || []).find((k) => k.id === d.id);
    if (c) verCompromisso(c);
    return;
  }
  if (d.tela === "financeiro") return abrirDestino("financeiro");
  if (d.tela === "publicacao") return abrirPublicacoesBsc(d.id);
  if (d.tela === "processo") { await mostrarProcessos(); return abrirProcesso(d.id); }
  if (d.tela === "conflito" && typeof abrirConflito === "function") return abrirConflito(d.id);
  if (d.tela === "documento") return verNoAcervo(d.nome);
  if (d.tela === "aprovacoes") return abrirDestino("aprovacoes");
  if (d.tela === "nfse" && typeof abrirNotaFiscal === "function") return abrirNotaFiscal(d.id);
  if (d.tela === "conversa") return abrirTrabalho(d.id);
  if (d.tela === "foco") return abrirDestino("foco");
}

/* A acao direta sempre pergunta antes, com o que ela faz em palavras. E a
   rota da tela de origem: concluir aqui e concluir em Tarefas. */
async function fazerAcaoDoAviso(a, i) {
  const x = (a.acoes || [])[i];
  if (!x) return;
  const ok = await confirmar({
    titulo: x.propoe ? "Propor: " + x.pergunta : x.pergunta,
    contexto: "Avisos › " + a.tipo_rotulo,
    texto: x.explica + (x.propoe ? "\nPelo acesso de fora, isto vira um pedido em Aprovações e só acontece depois do sim de quem pode." : ""),
    confirmar: x.propoe ? "Propor" : x.rotulo,
  });
  if (ok) {
    let r;
    try {
      r = await fetch(x.rota, { method: x.metodo || "POST", headers: AV_JSON, body: JSON.stringify(x.corpo || {}) });
    } catch (err) {
      r = null;
    }
    if (!r || (!r.ok && r.status !== 202)) {
      avisoCert(r ? await erroDe(r) : "não consegui falar com o programa", { tom: "erro" });
    } else {
      let d = {};
      try { d = await r.json(); } catch (err) { /* sem corpo */ }
      if (r.status === 202 || d.proposto) avisoCert("pedido enviado para Aprovações", { tom: "ok" });
      else if (x.id === "vistas") avisoCert("movimentações marcadas como vistas", { tom: "ok" });
      else if (x.id === "concluir") avisoCert("tarefa concluída" + (d.aviso_repeticao ? " — " + d.aviso_repeticao : ""), { tom: "ok" });
      else avisoCert(/recebido/i.test(x.rotulo) ? "recebimento registrado hoje" : "pagamento registrado hoje — anexe o comprovante no Financeiro", { tom: "ok" });
    }
  }
  await carregarAvisosDoDia(true);
  if (painelDeAvisosAberto()) recarregarPainelDeAvisos();
}

/* ---------------------------------------------------------- o painel */
/*
   O painel na tela inicial (no lugar da lista de conversas): a coluna dos tipos, com a conta de cada um, e a lista agrupada.
   A busca e o periodo (Hoje, 7 dias, 30 dias) moram no cabecalho de quem
   o recebe.
*/

function painelDeAvisosAberto() {
  return Boolean(document.querySelector("[data-av-painel]"));
}

async function recarregarPainelDeAvisos() {
  const p = avs.painel;
  try {
    if (p.tipo === "historico") {
      const r = await fetch("/api/central-avisos/historico");
      p.historico = r.ok ? await r.json() : { itens: [] };
    } else {
      const r = await fetch("/api/central-avisos?periodo=" + encodeURIComponent(p.periodo) + "&tipo=");
      p.dados = r.ok ? await r.json() : { avisos: [] };
    }
  } catch (err) {
    /* desenha com o que houver */
  }
  document.querySelectorAll("[data-av-painel]").forEach((el) => desenharPainelDeAvisos(el));
}

/* O que a lista mostra: o periodo do servidor, o tipo escolhido e a busca. */
function avisosDoPainel() {
  const p = avs.painel;
  const termo = semAcento(p.termo || "");
  return ((p.dados && p.dados.avisos) || []).filter((a) => {
    if (p.tipo && p.tipo !== "todos" && !p.tipo.startsWith("grupo:") && a.tipo !== p.tipo) return false;
    if (p.tipo === "grupo:atrasado" && a.grupo !== "atrasado") return false;
    if (p.tipo === "grupo:hoje" && !(a.grupo === "hoje" && !ehConversaPelaMetade(a))) return false;
    if (p.tipo === "grupo:conversas" && !ehConversaPelaMetade(a)) return false;
    if (!termo) return true;
    return semAcento(a.titulo + " " + a.tipo_rotulo + " " + a.quando + " " + a.origem + " " + (a.detalhe || "")).includes(termo);
  });
}

function semAcento(texto) {
  return String(texto || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function navDoPainel(todos) {
  const p = avs.painel;
  const conta = {};
  todos.forEach((a) => { if (!a.visto) conta[a.tipo] = (conta[a.tipo] || 0) + 1; });
  const total = todos.filter((a) => !a.visto).length;
  const item = (id, rotulo, icone, n) => {
    const ativo = (p.tipo || "todos") === id;
    return '<button type="button" class="avp-tipo' + (ativo ? " ativo" : "") + (n ? "" : " vazio") + '" data-avp-tipo="' + id + '">' +
      ic(icone, 15) + "<span>" + esc(rotulo) + '</span><small>' + (n || "–") + "</small></button>";
  };
  return '<nav class="avp-nav">' + item("todos", "Todos", "inbox", total) +
    AV_GAVETAS.map(([gaveta, tipos]) => '<div class="avp-gaveta">' + esc(gaveta) + "</div>" +
      tipos.map((t) => item(t, AV_ROTULO[t], AV_ICONE[t], conta[t] || 0)).join("")).join("") +
    '<button type="button" class="avp-historico' + (p.tipo === "historico" ? " ativo" : "") + '" data-avp-tipo="historico">Histórico · já resolvidos</button></nav>';
}

function linhaDoPainel(a) {
  const marca = a.visto
    ? '<button type="button" class="av-marca" data-av-desmarcar="' + esc(a.id) + '" title="Visto — desmarcar" aria-label="Desmarcar: ' + esc(a.titulo) + '"><span class="ic ic-18 ag-feita-ic">check_circle</span></button>'
    : '<button type="button" class="av-marca" data-av-visto="' + esc(a.id) + '" title="Marcar como visto" aria-label="Marcar como visto: ' + esc(a.titulo) + '"><span class="ag-circulo"></span></button>';
  const acao = ehConversaPelaMetade(a)
    ? '<button type="button" class="avp-acao" data-av-abrir="' + esc(a.id) + '">Continuar</button>'
    : (a.acoes || []).map((x, i) => '<button type="button" class="avp-acao" data-av-acao="' + esc(a.id) + '" data-av-i="' + i + '">' + esc(rotuloDaAcao(x)) + "</button>").join("");
  const origem = String(a.origem || "").split(" · ");
  const sub = [a.tipo_rotulo].concat(origem.slice(1), [a.detalhe]).filter(Boolean).join(" · ");
  return '<div class="avp-linha' + (a.grupo === "atrasado" ? " avp-atrasada" : "") + (a.visto ? " av-visto" : "") + '" data-sel="' + esc(a.id) + '" data-av="' + esc(a.id) + '">' +
    marca + '<span class="avp-ic">' + ic(iconeDoAviso(a), 15) + "</span>" +
    '<span class="avp-texto"><b>' + esc(a.titulo) + "</b><small>" + esc(sub) + "</small></span>" +
    '<span class="avp-col avp-quando">' + esc(a.quando || "") + '</span><span class="avp-col avp-onde">' + esc(origem[0]) + "</span>" +
    '<span class="avp-acoes">' + acao + '<button type="button" class="avp-abrir" data-av-abrir="' + esc(a.id) + '">Abrir</button></span></div>';
}

function listaDoPainel() {
  const p = avs.painel;
  if (p.tipo === "historico") {
    const h = p.historico || { itens: [] };
    const termo = semAcento(p.termo || "");
    const itens = (h.itens || []).filter((l) => !termo || semAcento(l.titulo + " " + l.origem).includes(termo));
    return '<p class="avp-nota">' + (h.titular ? "Os vistos de todos da equipe. Cada pessoa desmarca os próprios." : "Os avisos que você marcou como visto, com o que diziam naquele momento.") + "</p>" +
      (itens.length ? itens.map(linhaDoHistoricoDeAvisos).join("") : '<p class="av-vazio">Nada marcado como visto ainda.</p>');
  }
  const lista = avisosDoPainel();
  if (!p.dados) return esqueleto("lista");
  if (!lista.length) return '<p class="av-vazio">' + (p.termo ? "Nenhum aviso com essa busca." : "Nada por ver neste período. Tudo em dia por aqui.") + "</p>";
  const grupos = new Map(AV_GRUPOS.map(([g]) => [g, []]));
  lista.forEach((a) => {
    const g = ehConversaPelaMetade(a) ? "conversas" : a.grupo;
    (grupos.get(g) || grupos.get("depois")).push(a);
  });
  return AV_GRUPOS.filter(([g]) => grupos.get(g).length).map(([g, rotulo, tom]) => {
    const itens = grupos.get(g);
    const aberto = p.abertos.has(g) || itens.length <= AV_POR_GRUPO + 1;
    const resto = itens.length - AV_POR_GRUPO;
    const nome = g === "conversas" ? "conversa" : "aviso";
    const classe = "avp-ponto " + tom;
    return '<div class="avp-grupo"><div class="avp-grupo-cabeca"><i class="' + classe + '"></i>' + esc(rotulo) + "<small>" + itens.length + "</small></div>" +
      (aberto ? itens : itens.slice(0, AV_POR_GRUPO)).map(linhaDoPainel).join("") +
      (aberto ? "" : '<button type="button" class="avp-mais" data-avp-mais="' + g + '">mais ' + plural(resto, nome) + "</button>") + "</div>";
  }).join("");
}

function linhaDoHistoricoDeAvisos(l) {
  const onde = l.de_onde === "remoto" ? "pelo acesso de fora" : "no computador do escritório";
  return '<div class="avp-linha av-visto" data-av-hist="' + esc(l.aviso_id) + '">' +
    '<span class="avp-ic">' + ic(AV_ICONE[l.tipo] || "history", 15) + "</span>" +
    '<span class="avp-texto"><b>' + esc(l.titulo) + "</b><small>" + esc(l.tipo_rotulo) + " · dizia “" + esc(l.quando) + "” · " + esc(l.origem) +
    " · visto por " + esc(l.pessoa_nome || (l.pessoa === "local" ? "quem está no escritório" : "conta de fora")) + " em " + esc(horaCurta(l.visto_em)) + ", " + onde + "</small></span>" +
    '<span class="avp-acoes">' + (l.meu ? '<button type="button" class="avp-abrir" data-av-desmarcar="' + esc(l.aviso_id) + '">Desmarcar</button>' : "") + "</span></div>";
}

function horaCurta(isoTexto) {
  const t = String(isoTexto || "");
  if (t.length < 16) return t;
  return t.slice(8, 10) + "/" + t.slice(5, 7) + " às " + t.slice(11, 16);
}

/* A barra com a busca e o periodo: na tela inicial ela fica no cabecalho do
   cartao. */
function barraDoPainel() {
  const p = avs.painel;
  const periodos = [["hoje", "Hoje"], ["semana", "7 dias"], ["mes", "30 dias"]].map(([v, r]) => {
    const classe = p.periodo === v ? "ativa" : "";
    return '<button type="button" data-avp-periodo="' + v + '" class="' + classe + '">' + r + "</button>";
  }).join("");
  return '<label class="busca-tela avp-busca">' + ic("search", 16) +
    '<input type="text" data-avp-busca="1" placeholder="Buscar nos avisos…" value="' + esc(p.termo) + '"></label>' +
    '<span class="visoes avp-periodos">' + periodos + "</span>";
}

function desenharPainelDeAvisos(raiz) {
  const p = avs.painel;
  const corpo = raiz.querySelector("[data-avp-corpo]");
  if (!corpo) return;
  const todos = (p.dados && p.dados.avisos) || [];
  corpo.innerHTML = navDoPainel(todos) + '<div class="avp-lista">' + listaDoPainel() + "</div>";
  const conta = raiz.querySelector("[data-avp-conta]");
  if (conta) {
    const vivos = todos.filter((a) => !a.visto);
    const atrasados = vivos.filter((a) => a.grupo === "atrasado").length;
    conta.textContent = plural(vivos.length, "aviso") + (atrasados ? " · " + atrasados + (atrasados === 1 ? " atrasado" : " atrasados") : "");
  }
  const pe = raiz.querySelector("[data-avp-pe]");
  if (pe) {
    const n = p.escolhidos.size;
    pe.innerHTML = n
      ? barraDeSelecao(n, false, '<button type="button" class="avp-acao" data-avp-lote="visto">' + ic("check", 15) + "Marcar como visto</button>", "data-avp-limpar")
      : esc(plural(avisosDoPainel().filter((a) => !a.visto).length, "aviso")) + " · selecione vários para resolver de uma vez";
    const lote = pe.querySelector("[data-avp-lote]");
    if (lote) lote.onclick = () => marcarVistosEmLote([...p.escolhidos]);
    const limpar = pe.querySelector("[data-avp-limpar]");
    if (limpar) limpar.onclick = () => { p.escolhidos.clear(); desenharPainelDeAvisos(raiz); };
  }
  raiz.querySelectorAll("[data-avp-tipo]").forEach((b) => {
    b.onclick = () => {
      p.tipo = b.dataset.avpTipo === "todos" ? "" : b.dataset.avpTipo;
      p.escolhidos.clear();
      if (p.tipo === "historico") recarregarPainelDeAvisos();
      else if (!p.dados) recarregarPainelDeAvisos();
      else desenharPainelDeAvisos(raiz);
    };
  });
  raiz.querySelectorAll("[data-avp-mais]").forEach((b) => {
    b.onclick = () => { p.abertos.add(b.dataset.avpMais); desenharPainelDeAvisos(raiz); };
  });
  ligarLinhasDeAviso(corpo, () => todos);
  ligarSelecao(corpo.querySelector(".avp-lista"), {
    linhas: ".avp-linha[data-sel]", escolhidos: p.escolhidos, aoMudar: () => desenharPainelDeAvisos(raiz),
  });
  corpo.querySelectorAll(".avp-linha[data-sel]").forEach((linha) => {
    linha.onclick = () => { if (p.escolhidos.size) return; const a = avisoPorId(linha.dataset.av, todos); if (a) abrirAviso(a); };
  });
}

/* A barra (busca e periodo) e ligada uma vez por cabecalho: digitar nao
   pode perder o foco do campo a cada letra. */
function ligarBarraDoPainel(raiz) {
  const p = avs.painel;
  raiz.querySelectorAll("[data-avp-periodo]").forEach((b) => {
    b.onclick = () => {
      p.periodo = b.dataset.avpPeriodo;
      raiz.querySelectorAll("[data-avp-periodo]").forEach((x) => x.classList.toggle("ativa", x === b));
      if (p.tipo === "historico") p.tipo = "";
      recarregarPainelDeAvisos();
    };
  });
  const busca = raiz.querySelector("[data-avp-busca]");
  if (busca) {
    let relogio = null;
    busca.oninput = () => {
      clearTimeout(relogio);
      relogio = setTimeout(() => { p.termo = busca.value.trim(); document.querySelectorAll("[data-av-painel]").forEach(desenharPainelDeAvisos); }, 160);
    };
  }
}

async function marcarVistosEmLote(ids) {
  let feitos = 0;
  for (const id of ids) {
    try {
      const r = await fetch("/api/central-avisos/visto", { method: "POST", headers: AV_JSON, body: JSON.stringify({ id: id }) });
      if (r.ok) feitos += 1;
    } catch (err) { /* segue com os outros */ }
  }
  avs.painel.escolhidos.clear();
  avisoCert(plural(feitos, "aviso") + " " + (feitos === 1 ? "marcado" : "marcados") + " como visto — no Histórico dos avisos", { tom: "ok" });
  await carregarAvisosDoDia(true);
  recarregarPainelDeAvisos();
}

/* ----------------------------------------- o painel no lugar da lista */

function abrirAvisosNaInicio(filtro) {
  const p = avs.painel;
  avs.naInicio = true;
  p.tipo = filtro ? (filtro === "conversas" || filtro === "atrasado" || filtro === "hoje" ? "grupo:" + filtro : filtro) : "";
  p.periodo = "semana";
  p.abertos.clear();
  p.escolhidos.clear();
  desenharAvisos();
  recarregarPainelDeAvisos();
}

function fecharAvisosNaInicio() {
  avs.naInicio = false;
  const caixa = $("av-painel");
  if (caixa) { caixa.hidden = true; caixa.innerHTML = ""; }
  $("lista-conversas").hidden = !lembrancaDoInicio.lista;
  desenharRecentes();
  delete $("av-dia").dataset.assinatura;
  desenharAvisos();
}

function desenharPainelNaInicio() {
  const caixa = $("av-painel");
  if (!caixa) return;
  $("lista-conversas").hidden = true;
  $("recentes").hidden = true;
  if (caixa.hidden || !caixa.querySelector("[data-av-painel]")) {
    caixa.hidden = false;
    caixa.innerHTML = '<div class="avp-cartao" data-av-painel="inicio">' +
      '<div class="avp-cabeca"><span class="sv-kicker">Avisos</span><span class="avp-conta" data-avp-conta="1"></span><span class="vazio-flex"></span>' +
      barraDoPainel() +
      '<button type="button" class="botao-icone" data-avp-fechar="1" title="Voltar às conversas" aria-label="Voltar às conversas">' + ic("close", 16) + "</button></div>" +
      '<div class="avp" data-avp-corpo="1"></div><div class="avp-rodape"><span class="avp-pe" data-avp-pe="1"></span></div></div>';
    ligarBarraDoPainel(caixa);
    caixa.querySelector("[data-avp-fechar]").onclick = fecharAvisosNaInicio;
    if (animacoesLigadas()) entraConteudo(caixa.firstElementChild);
  }
  desenharPainelDeAvisos(caixa.firstElementChild);
}

(function () {
  const col = $("conversa-col");
  // A tela inicial aparece e some sem recarregar a pagina: a faixa
  // acompanha na hora, sem esperar o relogio.
  if (col && typeof MutationObserver === "function") {
    new MutationObserver(() => carregarAvisosDoDia(false)).observe(col, { attributes: true, attributeFilter: ["class"] });
  }
  window.addEventListener("focus", () => carregarAvisosDoDia(true));
  setInterval(() => carregarAvisosDoDia(false), 5000);
  carregarAvisosDoDia(true);
})();
