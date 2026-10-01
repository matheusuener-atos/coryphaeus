/* ------------------------------------------------------ avisos do dia */
/*
   T2 (docs/prompt-conversa-agentes-v0.md §2.7): o carrossel de avisos da
   tela inicial, logo abaixo de "Acontecendo agora", e a Central de avisos
   (Hoje, Todos, Histórico).

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
  // Um cartao so (pedido do dono, 30/09): o aviso da vez e onde ele esta.
  // Guardar o id faz a recarga de 30 s manter o mesmo cartao; quando ele sai
  // (visto, concluido), fica a posicao - e o proximo entra no lugar dele.
  atual: "", pos: 0,
  central: { aba: "hoje", tipo: "", periodo: "semana", hperiodo: "tudo", dados: null, historico: null },
};
const AV_RECARGA_MS = 30000;
const AV_JSON = { "Content-Type": "application/json" };

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

/* O cartao e o de "Acontecendo agora" (.cartao-agora): tipo, quando, titulo,
   de onde vem, Abrir e a acao direta. O circulo de marcar e o das tarefas
   (.ag-circulo). Atrasado ou de hoje tem o destaque discreto do sistema
   (--destaque-fundo), nunca a cor de erro. */
function cartaoDeAviso(a) {
  const acoes = (a.acoes || []).map((x, i) =>
    '<button type="button" data-av-acao="' + esc(a.id) + '" data-av-i="' + i + '">' + esc(rotuloDaAcao(x)) + "</button>").join("");
  return '<div class="cartao-agora av-cartao' + (a.destaque ? " av-destaque" : "") + '" role="listitem" tabindex="-1" data-av="' + esc(a.id) + '">' +
    '<div class="cabeca">' +
    '<button type="button" class="av-marca" data-av-visto="' + esc(a.id) + '" title="Marcar como visto" aria-label="Marcar como visto: ' + esc(a.titulo) + '">' +
    '<span class="ag-circulo"></span></button>' +
    '<span class="av-tipo">' + ic(a.icone || "notifications", 16) + "<span>" + esc(a.tipo_rotulo) + "</span></span></div>" +
    '<div class="av-titulo">' + esc(a.titulo) + "</div>" +
    '<div class="av-quando">' + esc(a.quando) + "</div>" +
    '<div class="rodape av-origem">' + esc(a.origem) + (a.detalhe ? " · " + esc(a.detalhe) : "") + "</div>" +
    '<div class="acoes"><button type="button" class="fantasma" data-av-abrir="' + esc(a.id) + '">Abrir</button>' + acoes + "</div>" +
    "</div>";
}

function rotuloDaAcao(x) {
  return x.propoe ? "Propor: " + x.rotulo.charAt(0).toLowerCase() + x.rotulo.slice(1) : x.rotulo;
}

function desenharAvisos(sentido) {
  const caixa = $("av-dia");
  const trilho = $("av-trilho");
  if (!caixa || !trilho) return;
  const lista = avs.avisos || [];
  // Vazio: sem avisos (ou com a chave desligada) os avisos nao aparecem.
  if (!avs.ligado || !lista.length || !avNaInicio()) {
    caixa.hidden = true;
    trilho.innerHTML = "";
    delete trilho.dataset.assinatura;
    return;
  }
  caixa.hidden = false;
  const achado = avs.atual ? lista.findIndex((a) => a.id === avs.atual) : -1;
  avs.pos = achado >= 0 ? achado : Math.min(Math.max(0, avs.pos), lista.length - 1);
  const a = lista[avs.pos];
  avs.atual = a.id;
  $("av-conta").textContent = lista.length === 1 ? "1 para ver" : (avs.pos + 1) + " de " + lista.length;
  atualizarSetas();
  const assinatura = a.id + "|" + a.quando + "|" + (a.acoes || []).length + "|" + lista.length;
  if (trilho.dataset.assinatura === assinatura) return;
  trilho.dataset.assinatura = assinatura;
  trilho.innerHTML = cartaoDeAviso(a);
  ligarCartoes(trilho);
  // A troca e um passo curto para o lado; com as animacoes reduzidas, nada.
  const cartao = trilho.firstElementChild;
  if (sentido && cartao && animacoesLigadas()) cartao.classList.add(sentido > 0 ? "av-vem-da-direita" : "av-vem-da-esquerda");
}

/* Anda de cartao em cartao: -1 volta, 1 avanca; "inicio"/"fim" vao as pontas. */
function irParaAviso(passo) {
  const lista = avs.avisos || [];
  if (!lista.length) return;
  const antes = avs.pos;
  if (passo === "inicio") avs.pos = 0;
  else if (passo === "fim") avs.pos = lista.length - 1;
  else avs.pos = Math.min(lista.length - 1, Math.max(0, avs.pos + passo));
  if (avs.pos === antes) return;
  avs.atual = lista[avs.pos].id;
  desenharAvisos(avs.pos > antes ? 1 : -1);
}

function avisoPorId(id, lista) {
  return (lista || avs.avisos || []).find((a) => a.id === id) ||
    ((avs.central.dados && avs.central.dados.avisos) || []).find((a) => a.id === id) || null;
}

function ligarCartoes(raiz) {
  raiz.querySelectorAll("[data-av-visto]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); marcarAvisoVisto(b.dataset.avVisto, b); };
  });
  raiz.querySelectorAll("[data-av-abrir]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); const a = avisoPorId(b.dataset.avAbrir); if (a) abrirAviso(a); };
  });
  raiz.querySelectorAll("[data-av-acao]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); const a = avisoPorId(b.dataset.avAcao); if (a) fazerAcaoDoAviso(a, Number(b.dataset.avI)); };
  });
  raiz.querySelectorAll("[data-av-central]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); abrirCentralDeAvisos(b.dataset.avCentral); };
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
    return;
  }
  if (!r.ok) {
    if (botao) botao.disabled = false;
    avisoCert(await erroDe(r), { tom: "erro" });
    carregarAvisosDoDia(true);
    return;
  }
  const d = await r.json();
  const cartao = botao ? botao.closest(".av-cartao, .av-linha") : null;
  if (botao) botao.innerHTML = '<span class="ic ic-18 ag-feita-ic">check_circle</span>';
  const depois = () => {
    avs.avisos = d.avisos || [];
    avs.carregadoEm = Date.now();
    // O visto sai; na mesma posicao entra o proximo (ou o anterior, no fim).
    if (avs.atual === id) avs.atual = "";
    desenharAvisos(1);
    if (centralAberta()) recarregarCentral();
  };
  // Marcado, o cartao sai com uma animacao curta - e, com as animacoes
  // reduzidas, sai na hora.
  if (cartao && cartao.classList.contains("av-cartao") && animacoesLigadas()) {
    cartao.classList.add("av-saindo");
    setTimeout(depois, 260);
  } else {
    depois();
  }
  avisoCert("marcado como visto — está no histórico da Central de avisos", {
    tom: "ok", acao: { rotulo: "Desfazer", fazer: () => desmarcarAviso(id) },
  });
}

async function desmarcarAviso(id) {
  const r = await fetch("/api/central-avisos/desmarcar", { method: "POST", headers: AV_JSON, body: JSON.stringify({ id: id }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  avs.avisos = d.avisos || [];
  avs.carregadoEm = Date.now();
  desenharAvisos();
  if (centralAberta()) recarregarCentral();
  avisoCert("desmarcado — o aviso voltou para a tela inicial", { tom: "ok" });
}

/* ------------------------------------------------------- abrir e agir */

async function abrirAviso(a) {
  const d = a.destino || {};
  fecharCentral();
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
  const voltar = centralAberta() ? avs.central.aba : null;
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
  // Concluido, o aviso sai da lista: o proximo fica no lugar (desenharAvisos
  // mantem a posicao quando o id da vez some).
  if (voltar) abrirCentralDeAvisos(voltar);
}

/* ------------------------------------------------- andar entre os avisos */

function atualizarSetas() {
  const n = (avs.avisos || []).length;
  const setas = $("av-setas");
  if (!setas) return;
  setas.hidden = n <= 1;
  $("av-ant").disabled = avs.pos <= 0;
  $("av-prox").disabled = avs.pos >= n - 1;
}

function ligarTrilho() {
  const t = $("av-trilho");
  if (!t || t.dataset.ligado) return;
  t.dataset.ligado = "1";
  $("av-ant").onclick = () => irParaAviso(-1);
  $("av-prox").onclick = () => irParaAviso(1);
  const todos = $("av-ver-todos");
  if (todos) todos.onclick = () => abrirCentralDeAvisos("todos");

  // Arrastar para o lado (mouse ou dedo) troca o cartao; o cartao nao rola.
  // Um arrasto nao vira clique no botao em que comecou.
  let arrasto = null;
  t.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    arrasto = { x: e.clientX, y: e.clientY, moveu: false };
  });
  window.addEventListener("pointermove", (e) => {
    if (!arrasto) return;
    if (!arrasto.moveu && Math.abs(e.clientX - arrasto.x) > 8 && Math.abs(e.clientX - arrasto.x) > Math.abs(e.clientY - arrasto.y)) {
      arrasto.moveu = true;
      t.classList.add("arrastando");
    }
  });
  window.addEventListener("pointerup", (e) => {
    if (arrasto && arrasto.moveu) {
      const dx = e.clientX - arrasto.x;
      if (Math.abs(dx) > 40) irParaAviso(dx < 0 ? 1 : -1);
      t.dataset.arrastou = "1";
      setTimeout(() => { delete t.dataset.arrastou; }, 0);
    }
    arrasto = null;
    t.classList.remove("arrastando");
  });
  t.addEventListener("click", (e) => {
    if (t.dataset.arrastou) { e.preventDefault(); e.stopPropagation(); }
  }, true);

  // Teclado: as setas trocam o cartao; Home e End vao ao primeiro e ao ultimo.
  t.addEventListener("keydown", (e) => {
    const passo = { ArrowRight: 1, ArrowLeft: -1, Home: "inicio", End: "fim" }[e.key];
    if (passo === undefined) return;
    e.preventDefault();
    irParaAviso(passo);
  });
}

/* ---------------------------------------------------- a Central de avisos */

function centralAberta() {
  return Boolean(document.querySelector("#veu-dialogo .av-central"));
}

function fecharCentral() {
  const b = document.querySelector("#veu-dialogo .av-central [data-dialogo='cancelar']");
  if (b) b.click();
}

async function abrirCentralDeAvisos(aba) {
  avs.central.aba = aba || avs.central.aba || "hoje";
  const pedido = dialogo({
    titulo: "Central de avisos", contexto: "Tela inicial › Avisos", classe: "av-central",
    html: '<div class="av-central-miolo" id="av-central-miolo">' + esqueleto("lista") + "</div>",
    confirmar: "Fechar", semCancelar: true,
  });
  await recarregarCentral();
  await pedido;
}

async function recarregarCentral() {
  const c = avs.central;
  try {
    if (c.aba === "historico") {
      const r = await fetch("/api/central-avisos/historico");
      c.historico = r.ok ? await r.json() : { itens: [] };
    } else {
      const periodo = c.aba === "hoje" ? "semana" : c.periodo;
      const r = await fetch("/api/central-avisos?periodo=" + encodeURIComponent(periodo) + "&tipo=" + encodeURIComponent(c.aba === "hoje" ? "" : c.tipo));
      c.dados = r.ok ? await r.json() : { avisos: [] };
    }
  } catch (err) {
    /* desenha com o que houver */
  }
  desenharCentral();
}

function desenharCentral() {
  const m = $("av-central-miolo");
  if (!m) return;
  const c = avs.central;
  const hoje = avs.avisos || [];
  const abas = [["hoje", "Hoje", hoje.length], ["todos", "Todos", null], ["historico", "Histórico", null]];
  let html = '<div class="visoes av-abas" role="tablist">' + abas.map(([aba, rotulo, n]) => {
    const ativa = c.aba === aba;
    return '<button type="button" role="tab" data-av-aba="' + aba + '" class="' + (ativa ? "ativa" : "") + '" aria-selected="' + ativa + '">' +
      esc(rotulo) + (n ? " <small>" + n + "</small>" : "") + "</button>";
  }).join("") + "</div>";

  if (c.aba === "hoje") {
    html += '<p class="av-nota">O que ainda não foi visto por você: atrasado, hoje, amanhã e esta semana. Visto não conclui nada.</p>';
    html += hoje.length ? '<div class="av-lista">' + hoje.map((a) => linhaDeAviso(a)).join("") + "</div>"
      : '<p class="av-vazio">Nada por ver. Tudo em dia por aqui.</p>';
  } else if (c.aba === "todos") {
    const d = c.dados || { avisos: [], tipos: [], periodos: [] };
    html += filtrosDaCentral(d.tipos || [], (d.periodos || []).map((p) => [p.id, p.rotulo]), c.periodo, "periodo");
    const lista = d.avisos || [];
    html += lista.length ? '<div class="av-lista">' + lista.map((a) => linhaDeAviso(a)).join("") + "</div>"
      : '<p class="av-vazio">Nenhum aviso ' + (c.tipo ? "desse tipo " : "") + "no período.</p>";
  } else {
    const h = c.historico || { itens: [] };
    const tipos = h.tipos || (c.dados && c.dados.tipos) || [];
    html += filtrosDaCentral(tipos, [["hoje", "Hoje"], ["semana", "7 dias"], ["mes", "30 dias"], ["tudo", "Tudo"]], c.hperiodo, "hperiodo");
    const itens = filtrarHistorico(h.itens || []);
    html += '<p class="av-nota">' + (h.titular ? "Os vistos de todos da equipe. Cada pessoa desmarca os próprios." : "Os avisos que você marcou como visto, com o que diziam naquele momento.") + "</p>";
    html += itens.length ? '<div class="av-lista">' + itens.map(linhaDoHistoricoDeAvisos).join("") + "</div>"
      : '<p class="av-vazio">Nada marcado como visto ' + (c.hperiodo === "tudo" ? "ainda" : "no período") + ".</p>";
  }
  if (avs.faltou && avs.faltou.length) html += '<p class="av-nota">Não consegui ler agora: ' + esc(avs.faltou.join(", ")) + ".</p>";
  m.innerHTML = html;

  m.querySelectorAll("[data-av-aba]").forEach((b) => {
    b.onclick = () => { c.aba = b.dataset.avAba; desenharCentral(); recarregarCentral(); };
  });
  m.querySelectorAll("[data-av-tipo]").forEach((b) => {
    b.onclick = () => { c.tipo = b.dataset.avTipo; c.aba === "historico" ? desenharCentral() : recarregarCentral(); };
  });
  m.querySelectorAll("[data-av-periodo]").forEach((b) => {
    b.onclick = () => { c[b.dataset.avChave] = b.dataset.avPeriodo; c.aba === "historico" ? desenharCentral() : recarregarCentral(); };
  });
  m.querySelectorAll("[data-av-desmarcar]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); desmarcarAviso(b.dataset.avDesmarcar); };
  });
  // Na lista da Central, o circulo e o mesmo; a linha nao some com animacao
  // (a lista se refaz), e na aba Todos o visto aparece marcado.
  m.querySelectorAll("[data-av-visto]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); marcarAvisoVisto(b.dataset.avVisto, b); };
  });
  const lista = c.aba === "todos" ? (c.dados && c.dados.avisos) : hoje;
  m.querySelectorAll("[data-av-abrir]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); const a = avisoPorId(b.dataset.avAbrir, lista); if (a) abrirAviso(a); };
  });
  m.querySelectorAll("[data-av-acao]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); const a = avisoPorId(b.dataset.avAcao, lista); if (a) fazerAcaoDoAviso(a, Number(b.dataset.avI)); };
  });
}

function filtrosDaCentral(tipos, periodos, periodoAtual, chave) {
  const c = avs.central;
  return '<div class="av-filtros">' +
    '<div class="ag-chips av-chips" aria-label="Tipo">' +
    '<button type="button" data-av-tipo="" class="' + (c.tipo ? "" : "on") + '">Todos os tipos</button>' +
    tipos.map((t) => '<button type="button" data-av-tipo="' + esc(t.id) + '" class="' + (c.tipo === t.id ? "on" : "") + '">' + esc(t.rotulo) + "</button>").join("") +
    "</div>" +
    '<div class="visoes av-periodos" aria-label="Período">' + periodos.map(([periodo, rotulo]) => {
      const classe = periodoAtual === periodo ? "ativa" : "";
      return '<button type="button" data-av-chave="' + chave + '" data-av-periodo="' + periodo + '" class="' + classe + '">' + esc(rotulo) + "</button>";
    }).join("") +
    "</div></div>";
}

function filtrarHistorico(itens) {
  const c = avs.central;
  const dias = { hoje: 0, semana: 7, mes: 30 }[c.hperiodo];
  const limite = dias === undefined ? "" : iso(new Date(Date.now() - dias * 86400000));
  return itens.filter((l) => (!c.tipo || l.tipo === c.tipo) && (!limite || String(l.visto_em).slice(0, 10) >= limite));
}

function linhaDeAviso(a) {
  const marca = a.visto
    ? '<button type="button" class="av-marca" data-av-desmarcar="' + esc(a.id) + '" title="Visto — desmarcar" aria-label="Desmarcar: ' + esc(a.titulo) + '"><span class="ic ic-18 ag-feita-ic">check_circle</span></button>'
    : '<button type="button" class="av-marca" data-av-visto="' + esc(a.id) + '" title="Marcar como visto" aria-label="Marcar como visto: ' + esc(a.titulo) + '"><span class="ag-circulo"></span></button>';
  const acoes = (a.acoes || []).map((x, i) =>
    '<button type="button" data-av-acao="' + esc(a.id) + '" data-av-i="' + i + '">' + esc(rotuloDaAcao(x)) + "</button>").join("");
  return '<div class="av-linha' + (a.destaque ? " av-destaque" : "") + (a.visto ? " av-visto" : "") + '" data-av="' + esc(a.id) + '">' + marca +
    '<span class="av-linha-ic">' + ic(a.icone || "notifications", 18) + "</span>" +
    '<span class="av-linha-texto"><b>' + esc(a.titulo) + "</b><small>" + esc(a.tipo_rotulo) + " · " + esc(a.quando) + " · " + esc(a.origem) +
    (a.visto ? " · visto " + esc(horaCurta(a.visto_em)) : "") + "</small></span>" +
    '<span class="av-linha-acoes">' + acoes + '<button type="button" class="fantasma" data-av-abrir="' + esc(a.id) + '">Abrir</button></span></div>';
}

function linhaDoHistoricoDeAvisos(l) {
  const onde = l.de_onde === "remoto" ? "pelo acesso de fora" : "no computador do escritório";
  return '<div class="av-linha av-visto" data-av-hist="' + esc(l.aviso_id) + '">' +
    '<span class="av-linha-ic">' + ic(l.icone || "history", 18) + "</span>" +
    '<span class="av-linha-texto"><b>' + esc(l.titulo) + "</b><small>" + esc(l.tipo_rotulo) + " · dizia “" + esc(l.quando) + "” · " + esc(l.origem) + "</small>" +
    '<small class="av-quem">Visto por ' + esc(l.pessoa_nome || (l.pessoa === "local" ? "quem está no escritório" : "conta de fora")) +
    " em " + esc(horaCurta(l.visto_em)) + ", " + onde + "</small></span>" +
    '<span class="av-linha-acoes">' + (l.meu ? '<button type="button" data-av-desmarcar="' + esc(l.aviso_id) + '">Desmarcar</button>' : "") + "</span></div>";
}

function horaCurta(isoTexto) {
  const t = String(isoTexto || "");
  if (t.length < 16) return t;
  return t.slice(8, 10) + "/" + t.slice(5, 7) + " às " + t.slice(11, 16);
}

/* A Central tambem abre pela busca (Ctrl+K), para quem marcou tudo como
   visto e quer o historico: sem avisos, o carrossel nao aparece. */
if (typeof acoesBsc === "function") {
  const acoesAntesDosAvisos = acoesBsc;
  // eslint-disable-next-line no-global-assign
  acoesBsc = function () {
    const a = acoesAntesDosAvisos();
    if (avs.ligado) {
      a.push({ grupo: "Ações", titulo: "Central de avisos", caminho: "Tela inicial › Avisos", icone: "notifications",
        descricao: "prazos, compromissos, contas e o histórico do visto",
        sinonimos: "avisos lembretes notificacoes historico visto prazos", fazer: () => abrirCentralDeAvisos("hoje") });
    }
    return a;
  };
}

(function () {
  ligarTrilho();
  const col = $("conversa-col");
  // A tela inicial aparece e some sem recarregar a pagina: o carrossel
  // acompanha na hora, sem esperar o relogio.
  if (col && typeof MutationObserver === "function") {
    new MutationObserver(() => carregarAvisosDoDia(false)).observe(col, { attributes: true, attributeFilter: ["class"] });
  }
  window.addEventListener("focus", () => carregarAvisosDoDia(true));
  setInterval(() => carregarAvisosDoDia(false), 5000);
  carregarAvisosDoDia(true);
})();
