/* ------------------------------------------------------------- agenda */
/*
   A Agenda do desenho (docs/ui/03-telas-desktop.md, A4) junta o que eram
   tres telas: Calendario, Agendamento e Tarefas viram as visoes Mes, Semana
   e Tarefas de uma tela so, com o painel a direita. O que tinha motor
   continua ligado nele: a grade (/api/agenda), o dia (/api/agenda/dia), os
   horarios livres (/api/agenda/livres) e as tarefas (/api/tarefas). Pedido
   pelo link e reuniao criada pelo programa ainda nao existem, e a tela diz.
*/

const ag = {
  visao: "mes",          // mes | semana | tarefas
  mes: null,             // Date do primeiro dia do mes visto
  semana: null,          // iso da segunda-feira da semana vista
  dia: null,             // iso do dia escolhido
  grade: null,           // /api/agenda do periodo visto
  diaAberto: null,       // /api/agenda/dia do dia escolhido
  painel: "dia",         // dia | form | tarefa | sugestoes
  form: null,            // o compromisso (ou tarefa) em edicao
  sugestoes: [],
  itens: {},             // os itens desenhados na grade, por chave
  largo: false,
  zoom: "dias",          // dias | meses | anos - o calendario do mes, como o miniatura
  tar: { filtro: "meu_dia", lista: "", itens: [], contagens: {}, listas: [],
         clientes: [], repeticoes: [], aberta: null, escolhidas: new Set() },
};

const AG_JSON = { "Content-Type": "application/json" };
const MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const DIAS_NOME = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];
const DIAS_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
const HORA_INICIO = 7;
const HORA_FIM = 20;
const FILTROS_TAREFA = [
  { id: "meu_dia", rotulo: "Meu dia" },
  { id: "importante", rotulo: "Importante" },
  { id: "planejadas", rotulo: "Planejadas" },
  { id: "concluidas", rotulo: "Concluídas" },
];
const NOME_DO_TIPO = {
  compromisso: ["Novo compromisso", "Editar compromisso"],
  pagamento: ["Novo pagamento", "Editar pagamento"],
  prazo_interno: ["Novo prazo interno", "Editar prazo interno"],
  tarefa: ["Nova tarefa", "Editar tarefa"],
};
const LEGENDA_DA_AGENDA = {
  compromisso: "Compromisso", prazo: "Prazo", pedido: "Pedido pelo link",
  tarefa: "Tarefa", documento: "Data em documento", pagamento: "Pagamento",
};
const SALAS = {
  meet: "https://meet.google.com/new",
  teams: "https://teams.microsoft.com/l/meeting/new",
};

/* ------------------------------------------------------ datas em texto */

function iso(d) {
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") +
         "-" + String(d.getDate()).padStart(2, "0");
}

function deIso(chave) {
  const [a, m, d] = chave.split("-").map(Number);
  return new Date(a, m - 1, d);
}

function andarDias(d, n) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function segundaDe(d) {
  return andarDias(d, -((d.getDay() + 6) % 7));
}

function maiuscula(t) {
  return t ? t[0].toUpperCase() + t.slice(1) : t;
}

/* "sexta, 11 de setembro" */
function diaPorExtenso(chave) {
  const d = deIso(chave);
  return DIAS_NOME[d.getDay()].toLowerCase() + ", " + d.getDate() + " de " + MESES_NOME[d.getMonth()];
}

/* "sex 11/09" */
function diaCurto(chave) {
  const d = deIso(chave);
  return DIAS_CURTOS[(d.getDay() + 6) % 7].toLowerCase() + " " + d.getDate() + "/" +
    String(d.getMonth() + 1).padStart(2, "0");
}

function duracaoEmTexto(min) {
  min = Number(min) || 0;
  if (min < 60) return min + " min";
  const h = Math.floor(min / 60), r = min % 60;
  return h + " h" + (r ? " " + String(r).padStart(2, "0") : "");
}

function proximaHoraCheia() {
  const h = Math.min(19, Math.max(8, new Date().getHours() + 1));
  return String(h).padStart(2, "0") + ":00";
}

/* Como o prazo aparece: em vinho quando ja passou ou e hoje. */
function quandoDaTarefa(t) {
  if (t.concluida) return { texto: "", acc: false };
  if (!t.prazo) return { texto: "sem prazo", acc: false };
  const s = t.situacao || "";
  if (s.indexOf("atrasada") === 0) return { texto: s.replace("dia(s)", "dias").replace("1 dias", "1 dia"), acc: true };
  if (s === "hoje") return { texto: "hoje", acc: true };
  if (s === "amanhã") return { texto: "até " + dataCurta(t.prazo), acc: true };
  return { texto: s, acc: false };
}

function criadaHa(quando) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(quando || "");
  if (!m) return "";
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const dias = Math.round((hoje - d) / 86400000);
  if (dias <= 0) return "Criada hoje";
  if (dias === 1) return "Criada ontem";
  return "Criada há " + dias + " dias";
}

/* --------------------------------------------------------- a tela */

/* Os tres destinos antigos continuam existindo no servidor e em quem os
   chama; cada um abre a Agenda na visao que o substituiu. */
function mostrarCalendario() { return mostrarAgenda("mes"); }
function mostrarAgendamento() { return mostrarAgenda("semana"); }
function mostrarTarefas() { return mostrarAgenda("tarefas"); }

async function mostrarAgenda(visao) {
  abrirTela("Agenda", { cheia: true });
  marcarDestino("calendario");

  const trocou = Boolean(visao) && visao !== ag.visao;
  if (visao) ag.visao = visao;
  const h = new Date();
  if (!ag.mes) ag.mes = new Date(h.getFullYear(), h.getMonth(), 1);
  if (!ag.semana) ag.semana = iso(segundaDe(h));
  if (!ag.dia) ag.dia = iso(h);
  if (trocou) {
    ag.zoom = "dias";
    ag.form = null;
    ag.painel = ag.visao === "tarefas" ? "tarefa" : (ag.visao === "semana" ? "form" : "dia");
  }
  if (ag.painel === "form" && !ag.form) ag.form = compromissoEmBranco();

  cabecalhoAgenda();
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">abrindo a agenda…</p></div></div>';
  try {
    await carregarAgenda();
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharAgenda();
  atualizarPostura();
}

function compromissoEmBranco(tipo) {
  return { tipo: tipo || "compromisso", data: ag.dia, hora: proximaHoraCheia(), duracao: 60,
           onde: (tipo || "compromisso") === "compromisso" ? "online" : "", avisar_min: 30 };
}

/* O cabeçalho é o da página - "Agenda" -, com as visões e o Novo. O mês (ou a
   semana) e as setas ficam dentro do calendário, como no calendário
   miniatura. */
function cabecalhoAgenda() {
  $("nav-tela").innerHTML = "";

  $("acoes-tela").innerHTML =
    '<div class="visoes">' +
    [["mes", "Mês"], ["semana", "Semana"], ["tarefas", "Tarefas"]].map(([v, r]) => {
      const classe = v === ag.visao ? "ativa" : "";
      return '<button class="' + classe + '" data-visao="' + v + '">' + r + "</button>";
    }).join("") + "</div>" +
    '<div class="com-menu"><button class="primario com-icone" id="ag-novo">Novo' + ic("expand_more", 16) + "</button></div>";
  $("acoes-tela").querySelectorAll("[data-visao]").forEach((b) => { b.onclick = () => mostrarAgenda(b.dataset.visao); });
  $("ag-novo").onclick = (e) => {
    e.stopPropagation();
    menuNaLinha($("ag-novo"), [
      { icone: "event", rotulo: "Compromisso", acao: () => criarNaAgenda("compromisso") },
      { icone: "payments", rotulo: "Pagamento", acao: () => criarNaAgenda("pagamento") },
      { icone: "flag", rotulo: "Prazo interno", acao: () => criarNaAgenda("prazo_interno") },
      { icone: "task_alt", rotulo: "Tarefa", acao: () => criarNaAgenda("tarefa") },
      "-",
      { icone: "auto_awesome", rotulo: "Prazos lidos nos documentos", acao: abrirSugestoes },
    ]);
  };
}

function tituloDaAgenda() {
  const c = ag.tar.contagens || {};
  let titulo, meta;
  if (ag.visao === "mes") {
    titulo = "Agenda";
    const n = (ag.grade && ag.grade.contagem) || {};
    meta = plural(n.compromissos || 0, "compromisso") + " · " + plural(n.prazos || 0, "prazo") +
      " · " + plural(c.abertas || 0, "tarefa aberta", "tarefas abertas");
  } else if (ag.visao === "semana") {
    const seg = deIso(ag.semana), dom = andarDias(seg, 6);
    titulo = "Agenda";
    meta = "Semana de " + seg.getDate() +
      (seg.getMonth() !== dom.getMonth() ? " de " + MESES_NOME[seg.getMonth()] : "") +
      " a " + dom.getDate() + " de " + MESES_NOME[dom.getMonth()];
    const cs = (ag.grade && ag.grade.compromissos) || [];
    const por = (t) => cs.filter((x) => x.tipo === t).length;
    const prazos = por("prazo_interno") + ((ag.grade && ag.grade.contagem.prazos) || 0);
    meta = plural(por("compromisso"), "compromisso") + " · " + plural(por("pagamento"), "pagamento") +
      " · " + plural(prazos, "prazo");
  } else {
    const f = FILTROS_TAREFA.find((x) => x.id === ag.tar.filtro);
    titulo = "Agenda";
    const abertas = ag.tar.itens.filter((t) => !t.concluida).length;
    meta = (ag.tar.lista || (f ? f.rotulo : "Tarefas")) + " · " + plural(abertas, "tarefa") +
      " · " + plural(ag.tar.itens.length - abertas, "concluída");
  }
  $("conversa-titulo").textContent = titulo;
  $("conversa-meta").textContent = meta;
}

function irParaHojeNaAgenda() {
  const h = new Date();
  ag.zoom = "dias";
  ag.mes = new Date(h.getFullYear(), h.getMonth(), 1);
  ag.semana = iso(segundaDe(h));
  ag.dia = iso(h);
  if (ag.painel === "dia") ag.diaAberto = null;
  mostrarAgenda();
}

/* A faixa de cima do calendário: as setas, o mês (ou a semana) e Hoje. */
function topoDoCalendario(titulo, subir) {
  const rotulo = subir ? '<button type="button" class="cal-titulo ag-cal-titulo" data-ag-subir="1" title="' +
      (ag.zoom === "dias" ? "Ver os meses" : "Ver os anos") + '">' + esc(titulo) + "</button>"
    : '<b class="ag-cal-titulo">' + esc(titulo) + "</b>";
  return '<div class="ag-cal-topo"><div class="ag-cal-centro">' +
    '<button class="cal-seta" data-ag-andar="-1" title="Anterior" aria-label="Anterior">' + ic("chevron_left", 18) + "</button>" + rotulo +
    '<button class="cal-seta" data-ag-andar="1" title="Próximo" aria-label="Próximo">' + ic("chevron_right", 18) + "</button></div>" +
    '<button class="cal-rodape-botao ag-cal-hoje" data-ag-hoje="1">Hoje</button></div>';
}

/* OS MESES E OS ANOS, COMO NO CALENDÁRIO MINIATURA. Clicar no mês mostra os
   doze meses do ano; clicar de novo, os anos da década. Escolher um ano
   volta aos meses dele, e escolher um mês volta aos dias. */
function zoomDoCalendario() {
  const ano = ag.mes.getFullYear();
  const hoje = new Date();
  if (ag.zoom === "meses") {
    const celulas = MESES_NOME.map((nome, m) => {
      const classe = "cal-celula ag-zoom-celula" + (m === ag.mes.getMonth() ? " escolhido" : "") +
        (ano === hoje.getFullYear() && m === hoje.getMonth() ? " ag-hoje" : "");
      return '<button type="button" class="' + classe + '" data-ag-zoom-mes="' + m + '">' + maiuscula(nome) + "</button>";
    }).join("");
    return '<div class="ag-cartao ag-calendario">' + topoDoCalendario(String(ano), true) + '<div class="ag-zoom">' + celulas + "</div></div>";
  }
  const decada = Math.floor(ano / 10) * 10;
  let celulas = "";
  for (let a = decada - 1; a <= decada + 10; a++) {
    const classe = "cal-celula ag-zoom-celula" + (a < decada || a > decada + 9 ? " fora-do-mes" : "") + (a === ano ? " escolhido" : "") +
      (a === hoje.getFullYear() ? " ag-hoje" : "");
    celulas += '<button type="button" class="' + classe + '" data-ag-zoom-ano="' + a + '">' + a + "</button>";
  }
  return '<div class="ag-cartao ag-calendario">' + topoDoCalendario(decada + "–" + (decada + 9), false) + '<div class="ag-zoom">' + celulas + "</div></div>";
}

function andarAgenda(n) {
  // Nos meses a seta anda um ano; nos anos, uma década.
  if (ag.visao === "mes" && ag.zoom === "meses") { ag.mes = new Date(ag.mes.getFullYear() + n, ag.mes.getMonth(), 1); desenharAgenda(); return; }
  if (ag.visao === "mes" && ag.zoom === "anos") { ag.mes = new Date(ag.mes.getFullYear() + 10 * n, ag.mes.getMonth(), 1); desenharAgenda(); return; }
  if (ag.visao === "mes") ag.mes = new Date(ag.mes.getFullYear(), ag.mes.getMonth() + n, 1);
  else ag.semana = iso(andarDias(deIso(ag.semana), 7 * n));
  mostrarAgenda();
}

function criarNaAgenda(tipo) {
  if (tipo === "tarefa") return abrirFormAgenda({ tipo: "tarefa", prazo: ag.dia, lista: ag.tar.lista || "" });
  abrirFormAgenda(compromissoEmBranco(tipo));
}

/* ------------------------------------------------------------ dados */

function periodoVisto() {
  if (ag.visao === "semana") return [ag.semana, iso(andarDias(deIso(ag.semana), 6))];
  const cels = celulasDoMes();
  return [iso(cels[0].data), iso(cels[cels.length - 1].data)];
}

/* Segunda como primeiro dia: e a semana do escritorio. */
function celulasDoMes() {
  const primeiro = new Date(ag.mes.getFullYear(), ag.mes.getMonth(), 1);
  const ultimo = new Date(ag.mes.getFullYear(), ag.mes.getMonth() + 1, 0);
  const desloca = (primeiro.getDay() + 6) % 7;
  const celulas = [];
  for (let i = desloca; i > 0; i--) celulas.push({ data: andarDias(primeiro, -i), fora: true });
  for (let n = 1; n <= ultimo.getDate(); n++) {
    celulas.push({ data: new Date(ag.mes.getFullYear(), ag.mes.getMonth(), n), fora: false });
  }
  while (celulas.length % 7 !== 0) {
    celulas.push({ data: andarDias(celulas[celulas.length - 1].data, 1), fora: true });
  }
  return celulas;
}

async function carregarAgenda() {
  if (ag.visao === "tarefas") {
    const d = await (await fetch("/api/tarefas?filtro=" + ag.tar.filtro +
      "&lista=" + encodeURIComponent(ag.tar.lista))).json();
    Object.assign(ag.tar, { itens: d.tarefas, contagens: d.contagens, listas: d.listas,
                            clientes: d.clientes, repeticoes: d.repeticoes || [] });
    if (ag.tar.aberta && !ag.tar.itens.some((t) => t.id === ag.tar.aberta)) ag.tar.aberta = null;
    return;
  }
  const [de, ate] = periodoVisto();
  const pedidos = [fetch("/api/agenda?de=" + de + "&ate=" + ate), fetch("/api/tarefas?filtro=meu_dia")];
  const grade = await (await pedidos[0]).json();
  const tarefas = await (await pedidos[1]).json();
  ag.grade = grade;
  Object.assign(ag.tar, { contagens: tarefas.contagens, clientes: tarefas.clientes,
                          listas: tarefas.listas, repeticoes: tarefas.repeticoes || [] });
  if (ag.painel === "dia") await carregarDia();
}

async function carregarDia() {
  try {
    ag.diaAberto = await (await fetch("/api/agenda/dia?dia=" + ag.dia)).json();
  } catch (err) {
    ag.diaAberto = null;
  }
}

async function recarregarAgenda() {
  try {
    await carregarAgenda();
  } catch (err) {
    avisoCert("não consegui atualizar a agenda");
    return;
  }
  desenharAgenda();
}

/* ---------------------------------------------------------- desenho */

function desenharAgenda() {
  tituloDaAgenda();
  ag.itens = {};
  let principal;
  if (ag.visao === "mes") principal = ag.zoom === "dias" ? vistaMes() : zoomDoCalendario();
  else if (ag.visao === "semana") principal = vistaSemanaAgenda();
  else principal = vistaTarefas();
  const classe = "acervo agenda" + (ag.largo ? " painel-largo" : "");
  $("centro").innerHTML = '<div class="' + classe + '" id="agenda"><div class="acervo-principal">' +
    principal + "</div>" + painelDaAgenda() + "</div>";
  ligarAgenda();
}

function generoDaMarca(x) {
  if (x.genero === "compromisso") {
    return x.tipo === "pagamento" ? "pagamento" : (x.tipo === "prazo_interno" ? "prazo" : "compromisso");
  }
  return x.genero;
}

function chaveDoItem(x) {
  return x.genero + ":" + x.id;
}

function legendaDaAgenda(generos, dica) {
  return '<div class="ag-legenda">' + generos.map((g) => {
    const classe = "ag-" + g;
    return '<span class="' + classe + '"><i></i>' + LEGENDA_DA_AGENDA[g] + "</span>";
  }).join("") + '<span class="ag-dica">' + dica + "</span></div>";
}

/* O MÊS COMO O CALENDÁRIO MINIATURA, EM TAMANHO GRANDE. A faixa de cima traz
   as setas, o mês e Hoje; cada dia é o número num círculo (hoje com o fio de
   destaque, o dia escolhido cheio) e, embaixo, um ponto por tipo do que tem
   nele e a conta. Clicar escolhe o dia - o painel mostra tudo dele -, e o
   duplo clique marca um compromisso. */
function vistaMes() {
  const hoje = iso(new Date());
  const g = ag.grade;
  const titulo = maiuscula(MESES_NOME[ag.mes.getMonth()]) + " " + ag.mes.getFullYear();
  let html = '<div class="ag-cartao ag-calendario">' + topoDoCalendario(titulo, true) + '<div class="ag-dias">' +
    DIAS_CURTOS.map((d, i) => {
      const classe = i >= 5 ? "ag-fds" : "";
      return '<span class="' + classe + '">' + d + "</span>";
    }).join("") + '</div><div class="ag-mes">';

  for (const c of celulasDoMes()) {
    const dia = iso(c.data);
    const itens = g.dias[dia] || [];
    const fds = c.data.getDay() === 0 || c.data.getDay() === 6;
    const classe = "ag-cel" + (c.fora ? " ag-fora" : "") + (fds ? " ag-fds" : "") +
      (dia === hoje ? " ag-hoje" : "") + (dia === ag.dia ? " ag-escolhido" : "");
    const generos = [...new Set(itens.map(generoDaMarca))].slice(0, 4);
    const pontos = generos.map((x) => { const classe = "ag-ponto ag-" + x; return '<i class="' + classe + '"></i>'; }).join("");
    const dica = itens.map((x) => (x.hora ? x.hora + " " : "") + x.titulo).join("\n");
    html += '<div class="' + classe + '" data-ag-dia="' + dia + '"' + (dica ? ' title="' + esc(dica) + '"' : "") + ">" +
      '<span class="ag-cel-num"><b>' + c.data.getDate() + "</b></span>" +
      (itens.length ? '<span class="ag-pontos">' + pontos + "</span>" + '<small class="ag-cel-conta">' + plural(itens.length, "item", "itens") + "</small>" : "") +
      "</div>";
  }
  html += "</div>" + legendaDaAgenda(["compromisso", "prazo", "tarefa", "pagamento", "documento"],
    "Clique no dia para ver · duplo clique marca um compromisso") + "</div>";
  return html;
}

function marcaDoItem(x, dia) {
  const chave = chaveDoItem(x);
  ag.itens[chave] = { item: x, dia: dia };
  const classe = "ag-marca ag-" + generoDaMarca(x);
  const quando = x.hora ? x.hora : (x.genero === "prazo" ? "até" : "");
  return '<span class="' + classe + '" data-ag-item="' + esc(chave) + '" title="' +
    esc((x.hora ? x.hora + " " : "") + x.titulo) + '"><i></i>' +
    (quando ? "<b>" + quando + "</b>" : "") + "<span>" + esc(x.titulo) + "</span></span>";
}

/* Das 7 as 20, segunda a sexta: fora disso o escritorio raramente marca, e o
   que cair fora aparece numa faixa abaixo da grade em vez de sumir. */
function vistaSemanaAgenda() {
  const seg = deIso(ag.semana);
  const hoje = iso(new Date());
  const g = ag.grade;
  const dias = [0, 1, 2, 3, 4].map((i) => andarDias(seg, i));

  const cabeca = '<div class="ag-semana-dias"><span></span>' + dias.map((d) => {
    const k = iso(d);
    const classe = k === hoje ? "ag-hoje" : "";
    return '<span class="' + classe + '">' + DIAS_CURTOS[(d.getDay() + 6) % 7] + " " + d.getDate() +
      (k === hoje ? " · hoje" : "") + "</span>";
  }).join("") + "</div>";

  const semHora = dias.map((d) => (g.dias[iso(d)] || []).filter((x) => !x.hora));
  let diaTodo = "";
  if (semHora.some((l) => l.length)) {
    diaTodo = '<div class="ag-dia-todo"><div class="ag-rotulo-hora">dia todo</div>' + dias.map((d, i) => {
      const k = iso(d);
      const classe = k === hoje ? "ag-hoje" : "";
      return '<div class="' + classe + '">' + semHora[i].map((x) => blocoDaSemana(x, k)).join("") + "</div>";
    }).join("") + "</div>";
  }

  let grade = '<div class="ag-rolagem"><div class="ag-semana">';
  for (let h = HORA_INICIO; h <= HORA_FIM; h++) {
    grade += '<div class="ag-rotulo-hora">' + String(h).padStart(2, "0") + ":00</div>";
    dias.forEach((d) => {
      const k = iso(d);
      const naHora = (g.dias[k] || []).filter((x) => x.hora && Number(x.hora.split(":")[0]) === h);
      const classe = "ag-hora-cel" + (k === hoje ? " ag-hoje" : "");
      grade += '<div class="' + classe + '" data-ag-hora="' + k + "T" + String(h).padStart(2, "0") + ':00">' +
        naHora.map((x) => blocoDaSemana(x, k)).join("") + "</div>";
    });
  }
  grade += "</div></div>";

  const resto = [];
  [5, 6].forEach((i) => {
    const k = iso(andarDias(seg, i));
    (g.dias[k] || []).forEach((x) => resto.push({ item: x, dia: k }));
  });
  dias.forEach((d) => {
    const k = iso(d);
    (g.dias[k] || []).filter((x) => x.hora && (Number(x.hora.split(":")[0]) < HORA_INICIO ||
      Number(x.hora.split(":")[0]) > HORA_FIM)).forEach((x) => resto.push({ item: x, dia: k }));
  });
  const fora = resto.length
    ? '<div class="ag-fora-da-grade"><b>Fora da grade</b>' + resto.map((r) => {
        const chave = chaveDoItem(r.item);
        ag.itens[chave] = r;
        return '<span data-ag-item="' + esc(chave) + '">' + esc(diaCurto(r.dia)) +
          (r.item.hora ? " " + r.item.hora : "") + " · " + esc(r.item.titulo) + "</span>";
      }).join("") + "</div>"
    : "";

  const dom = andarDias(seg, 6);
  const tituloSemana = seg.getDate() + (seg.getMonth() !== dom.getMonth() ? " " + MESES_NOME[seg.getMonth()].slice(0, 3) : "") +
    " – " + dom.getDate() + " " + MESES_NOME[dom.getMonth()].slice(0, 3) + " " + dom.getFullYear();
  return '<div class="ag-cartao">' + topoDoCalendario(tituloSemana) + cabeca + diaTodo + grade + fora +
    legendaDaAgenda(["compromisso", "prazo", "pedido", "pagamento"], "Clique numa hora vazia para marcar") + "</div>";
}

function blocoDaSemana(x, dia) {
  const chave = chaveDoItem(x);
  ag.itens[chave] = { item: x, dia: dia };
  const genero = generoDaMarca(x);
  const classe = "ag-bloco ag-" + genero + (dia === iso(new Date()) && genero === "compromisso" ? " ag-hoje" : "");
  const rotulo = { pagamento: "Pagamento", prazo: "Prazo", tarefa: "Tarefa", documento: "Documento" }[genero] || x.hora;
  return '<div class="' + classe + '" data-ag-item="' + esc(chave) + '" title="' + esc(x.titulo) + '"><small>' +
    esc(rotulo) + "</small><span>" + esc(x.titulo) + "</span></div>";
}

/* -------------------------------------------------------- as tarefas */

function vistaTarefas() {
  const c = ag.tar.contagens || {};
  const listas = ag.tar.listas.slice();
  if (ag.tar.lista && !listas.some((l) => l.nome === ag.tar.lista)) listas.push({ nome: ag.tar.lista, abertas: 0 });

  const filtros = FILTROS_TAREFA.map((f) => {
    const classe = "ag-lista-item" + (!ag.tar.lista && f.id === ag.tar.filtro ? " ativa" : "");
    return '<button class="' + classe + '" data-ag-filtro="' + f.id + '"><span class="ag-nome">' + f.rotulo + "</span>" +
      (f.id === "concluidas" ? "" : contaDaLista(c[f.id] || 0, f.id === "importante")) + "</button>";
  });
  /* "Atribuidas a mim" pede equipe, que so existe quando Cadastros tiver. */
  filtros.splice(3, 0, '<button class="ag-lista-item adiante" data-ag-adiante="1" title="Quando houver equipe em Cadastros">' +
    '<span class="ag-nome">Atribuídas a mim</span></button>');

  const esquerda = '<div class="ag-listas">' + filtros.join("") +
    '<span class="ac-divisa"></span><span class="ac-secao">Minhas listas</span>' +
    (listas.length
      ? listas.map((l, i) => {
          const classe = "ag-lista-item" + (l.nome === ag.tar.lista ? " ativa" : "");
          return '<button class="' + classe + '" data-ag-lista="' + esc(l.nome) + '">' + corDaLista(i) +
            '<span class="ag-nome">' + esc(l.nome) + "</span>" + contaDaLista(l.abertas || 0, false) + "</button>";
        }).join("")
      : '<span class="ac-secao">nenhuma ainda</span>') +
    '<button class="ac-incluir" data-ag-nova-lista="1">+ nova lista</button></div>';

  const abertas = ag.tar.itens.filter((t) => !t.concluida);
  const feitas = ag.tar.itens.filter((t) => t.concluida);
  const prazoSugerido = ag.tar.filtro === "meu_dia" || ag.tar.filtro === "importante" ? iso(new Date()) : "";
  let corpo;
  if (!ag.tar.itens.length) {
    corpo = '<div class="ag-vazio"><h4>' + (ag.tar.filtro === "meu_dia" && !ag.tar.lista ? "Nada pendente para hoje" : "Nada aqui") + "</h4><p>" +
      (ag.tar.filtro === "meu_dia" && !ag.tar.lista
        ? "O que tem prazo para hoje, o que já venceu e o que você trouxe para o dia aparece nesta lista."
        : "Nenhuma tarefa " + (ag.tar.lista ? "nesta lista" : "neste filtro") + " ainda.") + "</p></div>";
  } else {
    corpo = abertas.map(linhaDaTarefa).join("") +
      (feitas.length ? '<div class="ag-secao">Concluídas · ' + feitas.length + "</div>" + feitas.map(linhaDaTarefa).join("") : "");
  }
  const direita = '<div class="ag-cartao"><div class="ag-adicionar">' +
    '<button class="ag-mais-botao" data-ag-add="1" title="Adicionar">' + ic("add", 18) + "</button>" +
    '<input type="text" data-ag-nova="1" placeholder="Adicionar uma tarefa…">' +
    '<input type="date" data-ag-nova-prazo="1" value="' + prazoSugerido + '" title="Prazo"></div>' +
    (ag.tar.escolhidas.size
      ? '<div class="barra-selecao ag-selecao">' + barraDeSelecao(ag.tar.escolhidas.size, true,
        '<button data-ag-sel-concluir="1">' + ic("task_alt", 16) + "Concluir</button><span class=\"divisa-v\"></span>" +
        '<button class="botao-icone perigo" data-ag-sel-apagar="1" title="Excluir" aria-label="Excluir">' + ic("delete", 18) + "</button>", "data-ag-sel-limpar") + "</div>"
      : "") +
    '<div class="tabela-corpo">' + corpo + "</div></div>";

  return '<div class="ag-tarefas">' + esquerda + direita + "</div>";
}

function contaDaLista(n, acc) {
  const classe = "ag-conta" + (acc && n ? " ag-acc" : "");
  return '<span class="' + classe + '">' + n + "</span>";
}

function corDaLista(i) {
  const classe = "ag-cor ag-c" + (i % 4);
  return '<i class="' + classe + '"></i>';
}

function linhaDaTarefa(t) {
  if (t.concluida) {
    const classeFeita = "ag-linha ag-feita" + (ag.tar.escolhidas.has(String(t.id)) ? " escolhida" : "");
    return '<div class="' + classeFeita + '" data-ag-tarefa="' + t.id + '" data-sel="' + t.id + '">' +
      '<span class="ic ic-18 ag-feita-ic" data-ag-concluir="' + t.id + '" title="Reabrir">check_circle</span>' +
      '<span class="ag-texto"><b>' + esc(t.titulo) + "</b></span></div>";
  }
  const classe = "ag-linha" + (ag.tar.aberta === t.id ? " aberta" : "") + (ag.tar.escolhidas.has(String(t.id)) ? " escolhida" : "");
  return '<div class="' + classe + '" data-ag-tarefa="' + t.id + '" data-sel="' + t.id + '">' +
    '<span class="ag-circulo ag-grande" data-ag-concluir="' + t.id + '" title="Concluir"></span>' +
    '<span class="ag-texto"><b>' + esc(t.titulo) + "</b><small>" + metaDaTarefa(t) + "</small></span>" +
    botaoEstrela(t) + "</div>";
}

function metaDaTarefa(t) {
  const q = quandoDaTarefa(t);
  const pecas = [];
  if (q.texto) pecas.push(q.acc ? '<span class="ag-acc">' + esc(q.texto) + "</span>" : "<span>" + esc(q.texto) + "</span>");
  if (t.cadastro_nome) pecas.push("<span>" + esc(t.cadastro_nome) + "</span>");
  if (t.lista && !ag.tar.lista) pecas.push("<span>" + esc(t.lista) + "</span>");
  if (t.etapas && t.etapas.length) pecas.push("<span>" + plural(t.etapas.length, "etapa") + "</span>");
  if (t.repetir) pecas.push("<span>repete</span>");
  return pecas.join("");
}

function botaoEstrela(t) {
  const classe = "ag-estrela" + (t.importante ? " on" : "");
  return '<button class="' + classe + '" data-ag-estrela="' + t.id + '" title="Importante">' +
    ic(t.importante ? "star" : "star_outline", 18) + "</button>";
}

/* ---------------------------------------------------------- o painel */

function painelDaAgenda() {
  if (ag.painel === "form" && ag.form) return painelFormAgenda();
  if (ag.painel === "sugestoes") return painelSugestoes();
  if (ag.visao === "tarefas") return painelDaTarefa();
  return painelDoDia();
}

/* O painel da Agenda tem a largura dele: a alça de alargar saiu. */
function alcaDoPainel() {
  return "";
}

function painelDoDia() {
  const d = ag.diaAberto;
  const titulo = maiuscula(diaPorExtenso(ag.dia));
  if (!d || d.dia !== ag.dia) {
    return '<aside class="acervo-painel">' + alcaDoPainel() + '<div class="rolagem"><div class="painel-vazio"><h3>' +
      titulo + "</h3><p>abrindo o dia…</p></div></div></aside>";
  }
  const comps = d.compromissos;
  const abertas = d.tarefas.filter((t) => !t.concluida);
  const feitas = d.tarefas.length - abertas.length;
  const total = comps.length + d.tarefas.length;
  const meta = total ? plural(total, "item", "itens") + " · " + plural(comps.length, "compromisso") + " · " + plural(d.tarefas.length, "tarefa") +
    (d.tarefas.length ? " (" + feitas + " feita" + (feitas === 1 ? "" : "s") + ")" : "") : "nada neste dia";
  const comAviso = comps.filter((c) => c.avisar_min).length;

  const linhas = comps.map((c) => {
    const genero = c.tipo === "pagamento" ? "pagamento" : (c.tipo === "prazo_interno" ? "prazo" : "compromisso");
    const classe = "ag-hora-linha ag-" + genero;
    const detalhe = [duracaoEmTexto(c.duracao), (c.onde_rotulo || "").toLowerCase(), c.cadastro_nome]
      .filter(Boolean).join(" · ");
    const acoes = c.onde === "online"
      ? '<span class="ag-acoes"><button class="primario" data-ag-reuniao="' + c.id + '">' + ic("videocam", 16) + "Criar reunião" + ic("expand_more", 16) + "</button>" +
        '<button data-ag-sala="meet">Meet</button><button data-ag-sala="teams">Teams</button></span>'
      : "";
    return { hora: c.hora || "", html: '<div class="' + classe + '"><span class="ag-hora">' + esc(c.hora) + '</span><span class="ag-corpo"><span>' +
      (genero === "prazo" ? "Prazo: " : "") + esc(c.titulo) + "</span><small>" + esc(detalhe) + "</small>" + acoes + "</span>" +
      '<button class="mais-linha" data-ag-mais="' + c.id + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>" };
  });

  // A tarefa entra na mesma lista: no lugar da hora, a marca de concluir.
  const tarefas = d.tarefas.map((t) => {
    const classe = "ag-hora-linha ag-tarefa ag-tarefa-dia" + (t.concluida ? " ag-feita" : "");
    const detalhe = ["tarefa", t.lista, t.cadastro_nome, t.importante && !t.concluida ? "importante" : ""].filter(Boolean).join(" · ");
    return { hora: "", html: '<div class="' + classe + '" data-ag-abrir-tarefa="' + t.id + '"><span class="ag-hora">' +
      (t.concluida
        ? '<span class="ic ic-18 ag-feita-ic" data-ag-concluir="' + t.id + '" title="Reabrir">check_circle</span>'
        : '<span class="ag-circulo" data-ag-concluir="' + t.id + '" title="Concluir"></span>') +
      '</span><span class="ag-corpo"><span>' + esc(t.titulo) + "</span><small>" + esc(detalhe) + "</small></span></div>" };
  });
  // Tudo numa lista: o que tem hora em ordem, e as tarefas do dia depois.
  const doDia = linhas.slice().sort((a, b) => a.hora.localeCompare(b.hora)).concat(tarefas);

  return '<aside class="acervo-painel">' + alcaDoPainel() + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3 class="ag-dia-titulo">' + titulo + '</h3><span class="meta">' + meta + "</span></span>" +
    '<span class="ag-sino" title="' + (comAviso ? plural(comAviso, "compromisso") + " com aviso" : "nenhum aviso marcado") + '">' +
    ic("notifications", 18) + (comAviso ? "<i></i>" : "") + "</span></div>" +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Compromissos e tarefas</span>' +
    '<button class="ag-ligacao" data-ag-marcar="1">+ novo</button></div>' +
    (doDia.length ? doDia.map((x) => x.html).join('<span class="ag-risco"></span>') : "<p>Nada neste dia.</p>") +
    '<button class="ag-ligacao" data-ag-nova-tarefa="1">+ tarefa rápida</button>' +
    '<span class="ag-entrada" data-ag-entrada-tarefa="1" hidden><input type="text" placeholder="O que precisa ser feito neste dia…">' +
    "<button>Adicionar</button></span></div>" +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Pedidos pelo link</span><span class="contagem">em breve</span></div>' +
    "<p>Quando a sua página de agendamento existir, quem pedir horário por ela aparece aqui, com Aceitar e Propor outro horário.</p></div>" +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Anotação do dia</span></div>' +
    '<textarea class="ag-nota" data-ag-nota="1" placeholder="Escreva uma nota para este dia…">' + esc(d.nota || "") + "</textarea></div>" +
    "</div></aside>";
}

function painelFormAgenda() {
  const v = ag.form;
  const novo = !v.id;
  const tarefa = v.tipo === "tarefa";
  const nomes = NOME_DO_TIPO[v.tipo] || NOME_DO_TIPO.compromisso;
  const sub = tarefa
    ? (v.prazo ? maiuscula(diaCurto(v.prazo)) : "sem prazo")
    : maiuscula(diaCurto(v.data || ag.dia)) + " · " + (v.hora || "");

  const chips = [["compromisso", "Compromisso"], ["pagamento", "Pagamento"], ["prazo_interno", "Prazo interno"], ["tarefa", "Tarefa"]]
    .map(([t, r]) => {
      const classe = t === v.tipo ? "on" : "";
      return '<button class="' + classe + '" data-ag-tipo="' + t + '">' + r + "</button>";
    }).join("");
  const clientes = '<option value="">' + (tarefa ? "nenhum" : "ninguém do cadastro") + "</option>" +
    ag.tar.clientes.map((k) => '<option value="' + k.id + '"' + (k.id === v.cadastro_id ? " selected" : "") + ">" + esc(k.nome) + "</option>").join("");

  let campos;
  if (tarefa) {
    campos =
      '<div class="ag-duas"><div class="ag-campo"><label>Prazo</label><input type="date" data-c="prazo" value="' + esc(v.prazo || "") + '"></div>' +
      '<div class="ag-campo"><label>Lista</label><input type="text" data-c="lista" list="ag-listas-dl" value="' + esc(v.lista || "") + '" placeholder="nenhuma">' +
      '<datalist id="ag-listas-dl">' + ag.tar.listas.map((l) => '<option value="' + esc(l.nome) + '">').join("") + "</datalist></div></div>" +
      '<div class="ag-campo"><label>Cliente</label><select data-c="cadastro_id">' + clientes + "</select></div>" +
      '<div class="ag-campo"><label>Anotação</label><textarea data-c="anotacao" placeholder="O que vale lembrar…">' + esc(v.anotacao || "") + "</textarea></div>";
  } else {
    const duracoes = [15, 30, 45, 60, 90, 120, 180];
    if (v.duracao && duracoes.indexOf(Number(v.duracao)) < 0) duracoes.push(Number(v.duracao));
    const ondes = [["online", "Reunião online"], ["escritorio", "No escritório"], ["telefone", "Telefone"], ["", "Sem local"]].map(([o, r]) => {
      const classe = o === (v.onde || "") ? "on" : "";
      return '<button class="' + classe + '" data-ag-onde="' + o + '">' + r + "</button>";
    }).join("");
    const classeConvite = "ag-toggle" + (v.convite ? " on" : "");
    campos =
      '<div class="ag-duas"><div class="ag-campo"><label>Data</label><input type="date" data-c="data" value="' + esc(v.data || "") + '"></div>' +
      '<div class="ag-campo"><label>Hora</label><input type="time" data-c="hora" value="' + esc(v.hora || "") + '"></div></div>' +
      '<div class="ag-duas"><div class="ag-campo"><label>Duração</label><select data-c="duracao">' +
      duracoes.sort((a, b) => a - b).map((m) => '<option value="' + m + '"' + (m === Number(v.duracao) ? " selected" : "") + ">" + duracaoEmTexto(m) + "</option>").join("") +
      "</select></div>" +
      '<div class="ag-campo"><label>Avisar antes</label><select data-c="avisar_min">' +
      [[0, "não avisar"], [10, "10 min antes"], [30, "30 min antes"], [60, "1 h antes"], [1440, "um dia antes"]].map(([m, r]) =>
        '<option value="' + m + '"' + (m === Number(v.avisar_min || 0) ? " selected" : "") + ">" + r + "</option>").join("") +
      "</select></div></div>" +
      '<div class="ag-campo"><label>Com quem</label><select data-c="cadastro_id">' + clientes + "</select></div>" +
      '<div class="ag-campo"><label>Onde</label><div class="ag-chips">' + ondes + "</div></div>" +
      '<div class="ag-campo"><label>Cabe nestes horários</label><div class="ag-chips" data-ag-livres="1"><span class="ag-vazio-chip">procurando…</span></div></div>' +
      '<div class="ag-campo"><label>Anotação</label><textarea data-c="anotacao" placeholder="Pauta, endereço, o que levar…">' + esc(v.anotacao || "") + "</textarea></div>" +
      '<div class="' + classeConvite + '" data-ag-convite="1"><span>Enviar convite por e-mail ao salvar</span><i></i></div>' +
      '<p class="ag-explica">O convite sai pelo seu e-mail e passa pela tela de Aprovações antes de ser enviado.</p>';
  }

  return '<aside class="acervo-painel">' + alcaDoPainel() + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + nomes[novo ? 0 : 1] + '</h3><span class="meta">' + esc(sub) + "</span></span>" +
    '<button class="voltar" data-ag-fechar="1" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="ag-form">' +
    '<div class="ag-campo"><label>O que vou agendar</label><div class="ag-chips">' + chips + "</div></div>" +
    '<div class="ag-campo"><label>Título</label><input type="text" data-c="titulo" value="' + esc(v.titulo || "") + '" placeholder="' +
    (tarefa ? "Adicionar uma tarefa…" : "Renovação — Fornecedor A") + '"></div>' +
    campos +
    '<div class="ag-form-rodape"><button class="ag-ligacao" data-ag-fechar="1">Cancelar</button>' +
    (novo ? "" : '<button class="ag-perigo-fino" data-ag-apagar="1">Excluir</button>') +
    '<span class="ag-aviso" data-ag-aviso="1"></span>' +
    '<button class="primario" data-ag-salvar="1">' + (tarefa ? (novo ? "Adicionar" : "Salvar") : (novo ? "Marcar" : "Salvar")) + "</button></div>" +
    "</div></div></aside>";
}

function painelDaTarefa() {
  const t = ag.tar.itens.find((x) => x.id === ag.tar.aberta);
  if (!t) {
    return '<aside class="acervo-painel">' + alcaDoPainel() + '<div class="rolagem"><div class="painel-vazio"><h3>Nenhuma tarefa aberta</h3>' +
      "<p>Clique numa tarefa para ver as etapas, o prazo e o que ela tem ligado.</p></div></div></aside>";
  }
  const feitas = t.etapas.filter((e) => e.feita).length;
  const q = quandoDaTarefa(t);
  const rep = ag.tar.repeticoes.length ? ag.tar.repeticoes : [{ valor: "", rotulo: "Não repete" }];
  const classeEstrela = "ag-estrela" + (t.importante ? " on" : "");
  const classePrazo = q.acc ? "ag-acc" : "";
  const classeMeuDia = "ag-ligacao" + (t.meu_dia ? "" : " ag-fraca");

  const etapas = t.etapas.map((e) => {
    const classe = "ag-tarefa-linha" + (e.feita ? " ag-feita" : "");
    return '<div class="' + classe + '" data-ag-etapa="' + e.id + '">' +
      (e.feita ? '<span class="ic ic-18 ag-feita-ic">check_circle</span>' : '<span class="ag-circulo"></span>') +
      '<span class="ag-texto">' + esc(e.titulo) + "</span></div>";
  }).join("");

  return '<aside class="acervo-painel">' + alcaDoPainel() + '<div class="rolagem">' +
    '<div class="ag-ficha-cabeca">' +
    (t.concluida
      ? '<span class="ic ic-18 ag-feita-ic" data-ag-concluir="' + t.id + '" title="Reabrir">check_circle</span>'
      : '<span class="ag-circulo ag-grande" data-ag-concluir="' + t.id + '" title="Concluir"></span>') +
    "<h3>" + esc(t.titulo) + "</h3>" +
    '<button class="' + classeEstrela + '" data-ag-estrela="' + t.id + '" title="Importante">' + ic(t.importante ? "star" : "star_outline", 18) + "</button>" +
    '<button class="voltar" data-ag-fechar-tarefa="1" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Etapas</span><span class="contagem">' +
    (t.etapas.length ? feitas + " de " + t.etapas.length : "nenhuma") + "</span></div>" + etapas +
    '<button class="ag-ligacao" data-ag-nova-etapa="1">+ próxima etapa</button>' +
    '<span class="ag-entrada" data-ag-entrada-etapa="1" hidden><input type="text" placeholder="Próxima etapa…"><button>Acrescentar</button></span></div>' +

    '<div class="painel-chaves">' +
    '<div class="ag-chave"><span>Meu dia</span><button class="' + classeMeuDia + '" data-ag-meu-dia="1">' + (t.meu_dia ? "já está" : "adicionar") + "</button></div>" +
    '<div class="ag-chave"><span>Lembrar-me</span><input type="time" data-ag-campo="lembrar_em" value="' + esc(t.lembrar_em || "") + '"></div>' +
    '<div class="ag-chave"><span>Prazo</span><input type="date" class="' + classePrazo + '" data-ag-campo="prazo" value="' + esc(t.prazo || "") + '"></div>' +
    '<div class="ag-chave"><span>Repetir</span><select data-ag-campo="repetir">' +
    rep.map((r) => '<option value="' + esc(r.valor) + '"' + ((t.repetir || "") === r.valor ? " selected" : "") + ">" + esc(r.rotulo) + "</option>").join("") + "</select></div>" +
    '<div class="ag-chave"><span>Cliente</span><select data-ag-campo="cadastro_id"><option value="">nenhum</option>' +
    ag.tar.clientes.map((k) => '<option value="' + k.id + '"' + (k.id === t.cadastro_id ? " selected" : "") + ">" + esc(k.nome) + "</option>").join("") + "</select></div>" +
    '<div class="ag-chave"><span>Lista</span><input type="text" data-ag-campo="lista" value="' + esc(t.lista || "") + '" placeholder="nenhuma"></div>' +
    "</div>" +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Ligado a</span><button class="ag-ligacao" data-ag-ligar="1">+ documento</button></div>' +
    '<div data-ag-vinculos="1"><p>carregando…</p></div>' +
    (t.cadastro_nome ? '<div class="ag-ligado-linha"><span>' + esc(t.cadastro_nome) + '</span><button data-ag-cadastro="1">cadastro</button></div>' : "") +
    (t.prazo ? '<div class="ag-ligado-linha"><span>Prazo no calendário · ' + esc(diaCurto(t.prazo)) + '</span><button class="ag-acc" data-ag-ver-dia="' + esc(t.prazo) + '">abrir</button></div>' : "") +
    "</div>" +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Anotação</span></div>' +
    '<textarea class="ag-nota" data-ag-campo="anotacao" placeholder="Escreva uma anotação…">' + esc(t.anotacao || "") + "</textarea></div>" +

    '<div class="ag-ficha-rodape"><small>' + criadaHa(t.criada_em) + '</small><button class="ag-perigo-fino" data-ag-apagar-tarefa="1">Excluir</button></div>' +
    "</div></aside>";
}

function painelSugestoes() {
  const s = ag.sugestoes || [];
  return '<aside class="acervo-painel">' + alcaDoPainel() + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Prazos lidos nos documentos</h3><span class="meta">' +
    (s.length ? plural(s.length, "data") + " que ainda não " + (s.length === 1 ? "virou" : "viraram") + " tarefa" : "nada a sugerir") + "</span></span>" +
    '<button class="voltar" data-ag-fechar="1" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="painel-bloco">' +
    (s.length
      ? "<p>Datas que o assistente já leu nos contratos abertos. Escolha as que quiser.</p>" +
        s.map((x, i) => '<div class="ag-ligado"><span class="duas-linhas"><b>' + esc(x.titulo) + "</b><small>" + dataLonga(x.prazo) +
          (x.cliente ? " · " + esc(x.cliente) : "") + '</small></span><button data-ag-aceitar="' + i + '">Criar</button></div>').join("")
      : "<p>Os documentos abertos não trazem data dentro dos próximos 90 dias, ou todas já viraram tarefa.</p>") +
    "</div></div></aside>";
}

/* -------------------------------------------------------- o que liga */

function ligarAgenda() {
  const raiz = $("agenda");

  raiz.querySelectorAll("[data-ag-andar]").forEach((b) => { b.onclick = () => andarAgenda(Number(b.dataset.agAndar)); });
  raiz.querySelectorAll("[data-ag-hoje]").forEach((b) => { b.onclick = () => irParaHojeNaAgenda(); });
  raiz.querySelectorAll("[data-ag-subir]").forEach((b) => {
    b.onclick = () => { ag.zoom = ag.zoom === "dias" ? "meses" : "anos"; desenharAgenda(); };
  });
  raiz.querySelectorAll("[data-ag-zoom-mes]").forEach((b) => {
    b.onclick = () => { ag.mes = new Date(ag.mes.getFullYear(), Number(b.dataset.agZoomMes), 1); ag.zoom = "dias"; mostrarAgenda(); };
  });
  raiz.querySelectorAll("[data-ag-zoom-ano]").forEach((b) => {
    b.onclick = () => { ag.mes = new Date(Number(b.dataset.agZoomAno), ag.mes.getMonth(), 1); ag.zoom = "meses"; desenharAgenda(); };
  });
  raiz.querySelectorAll("[data-ag-dia]").forEach((el) => {
    el.onclick = () => escolherDia(el.dataset.agDia);
    el.ondblclick = () => { ag.dia = el.dataset.agDia; criarNaAgenda("compromisso"); };
  });
  raiz.querySelectorAll("[data-ag-hora]").forEach((el) => {
    el.onclick = (e) => {
      if (e.target.closest("[data-ag-item]")) return;
      const [dia, hora] = el.dataset.agHora.split("T");
      ag.dia = dia;
      abrirFormAgenda(Object.assign(compromissoEmBranco("compromisso"), { data: dia, hora: hora }));
    };
  });
  raiz.querySelectorAll(".acervo-principal [data-ag-item]").forEach((el) => {
    el.onclick = (e) => { e.stopPropagation(); abrirItem(el.dataset.agItem); };
  });

  raiz.querySelectorAll("[data-ag-filtro]").forEach((b) => {
    b.onclick = () => { ag.tar.filtro = b.dataset.agFiltro; ag.tar.lista = ""; ag.tar.aberta = null; mostrarAgenda(); };
  });
  raiz.querySelectorAll("[data-ag-lista]").forEach((b) => {
    b.onclick = () => {
      ag.tar.lista = ag.tar.lista === b.dataset.agLista ? "" : b.dataset.agLista;
      ag.tar.aberta = null;
      mostrarAgenda();
    };
  });
  raiz.querySelectorAll("[data-ag-adiante]").forEach((b) => {
    b.onclick = () => avisoCert("quando houver equipe em Cadastros, as tarefas atribuídas a você aparecem aqui");
  });
  const novaLista = raiz.querySelector("[data-ag-nova-lista]");
  if (novaLista) novaLista.onclick = async () => {
    const nome = await perguntar({ titulo: "Nova lista", contexto: "Agenda › Tarefas", campo: { rotulo: "Nome da lista", placeholder: "Prazos do trimestre", icone: "format_list_bulleted" }, confirmar: "Criar" });
    if (!nome || !nome.trim()) return;
    ag.tar.lista = nome.trim();
    ag.tar.aberta = null;
    avisoCert("a lista “" + ag.tar.lista + "” nasce com a primeira tarefa que você criar nela");
    mostrarAgenda();
  };
  const nova = raiz.querySelector("[data-ag-nova]");
  if (nova) {
    const criar = async () => {
      if (!nova.value.trim()) { nova.focus(); return; }
      const prazo = raiz.querySelector("[data-ag-nova-prazo]").value;
      await criarTarefa({ titulo: nova.value.trim(), prazo: prazo, lista: ag.tar.lista });
    };
    raiz.querySelector("[data-ag-add]").onclick = criar;
    nova.onkeydown = (e) => { if (e.key === "Enter") criar(); };
  }
  ligarSelecao(raiz.querySelector(".ag-tarefas .tabela-corpo"), {
    linhas: ".ag-linha[data-sel]", escolhidos: ag.tar.escolhidas, aoMudar: desenharAgenda, apagar: (ids) => apagarTarefasEmLote(ids),
  });
  const selLimpar = raiz.querySelector("[data-ag-sel-limpar]");
  if (selLimpar) selLimpar.onclick = (e) => { e.stopPropagation(); ag.tar.escolhidas.clear(); desenharAgenda(); };
  const selApagar = raiz.querySelector("[data-ag-sel-apagar]");
  if (selApagar) selApagar.onclick = (e) => { e.stopPropagation(); apagarTarefasEmLote([...ag.tar.escolhidas]); };
  const selConcluir = raiz.querySelector("[data-ag-sel-concluir]");
  if (selConcluir) selConcluir.onclick = (e) => { e.stopPropagation(); concluirTarefasEmLote([...ag.tar.escolhidas]); };
  raiz.querySelectorAll("[data-ag-tarefa]").forEach((el) => {
    el.onclick = () => {
      const id = Number(el.dataset.agTarefa);
      ag.tar.aberta = ag.tar.aberta === id ? null : id;
      ag.form = null;
      ag.painel = "tarefa";
      desenharAgenda();
    };
  });
  raiz.querySelectorAll(".acervo-principal [data-ag-concluir]").forEach((el) => {
    el.onclick = (e) => {
      e.stopPropagation();
      const t = ag.tar.itens.find((x) => x.id === Number(el.dataset.agConcluir));
      if (t) concluirTarefa(t.id, !t.concluida);
    };
  });
  raiz.querySelectorAll(".acervo-principal [data-ag-estrela]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const t = ag.tar.itens.find((x) => x.id === Number(b.dataset.agEstrela));
      if (t) marcarImportante(t.id, !t.importante);
    };
  });

  ligarPainel();
}

function desenharPainel() {
  const velho = document.querySelector("#agenda .acervo-painel");
  if (!velho) return;
  velho.insertAdjacentHTML("afterend", painelDaAgenda());
  velho.remove();
  $("agenda").classList.toggle("painel-largo", ag.largo);
  ligarPainel();
}

function ligarPainel() {
  const p = document.querySelector("#agenda .acervo-painel");
  if (!p) return;
  p.querySelectorAll("[data-ag-fechar]").forEach((b) => { b.onclick = fecharPainelDaAgenda; });
  if (ag.painel === "form" && ag.form) return ligarFormAgenda(p);
  if (ag.painel === "sugestoes") return ligarSugestoes(p);
  if (ag.visao === "tarefas") return ligarFichaDaTarefa(p);
  ligarPainelDoDia(p);
}

async function fecharPainelDaAgenda() {
  ag.form = null;
  ag.painel = ag.visao === "tarefas" ? "tarefa" : "dia";
  if (ag.painel === "dia" && (!ag.diaAberto || ag.diaAberto.dia !== ag.dia)) await carregarDia();
  desenharPainel();
}

async function escolherDia(dia) {
  ag.dia = dia;
  ag.form = null;
  ag.painel = "dia";
  $("agenda").querySelectorAll("[data-ag-dia]").forEach((el) => {
    el.classList.toggle("ag-escolhido", el.dataset.agDia === dia);
  });
  await carregarDia();
  desenharPainel();
}

function abrirFormAgenda(v) {
  ag.form = v;
  ag.painel = "form";
  desenharPainel();
}

function abrirItem(chave) {
  const r = ag.itens[chave];
  if (!r) return;
  const x = r.item;
  if (x.genero === "compromisso") {
    const c = (ag.grade.compromissos || []).find((k) => k.id === x.id);
    if (c) abrirFormAgenda(Object.assign({}, c));
    return;
  }
  if (x.genero === "documento") {
    bib.termo = x.titulo;
    marcarDestino("biblioteca");
    return mostrarBiblioteca();
  }
  abrirTarefaNaAgenda(x.id, r.dia, x.genero === "tarefa");
}

/* A tarefa abre na visao Tarefas, no filtro em que ela esta. */
function abrirTarefaNaAgenda(id, dia, concluida) {
  const hoje = iso(new Date());
  ag.tar.filtro = concluida ? "concluidas" : (dia && dia > hoje ? "planejadas" : "meu_dia");
  ag.tar.lista = "";
  ag.tar.aberta = id;
  ag.form = null;
  mostrarAgenda("tarefas");
  ag.painel = "tarefa";
}

/* ------------------------------------------------ o painel do dia */

function ligarPainelDoDia(p) {
  const d = ag.diaAberto;
  if (!d) return;
  const compromisso = (el, nome) => d.compromissos.find((x) => x.id === Number(el.dataset[nome]));

  p.querySelectorAll("[data-ag-marcar]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      menuNaLinha(b, [
        { rotulo: "Compromisso", acao: () => criarNaAgenda("compromisso") },
        { rotulo: "Tarefa", acao: () => criarNaAgenda("tarefa") },
        { rotulo: "Prazo interno", acao: () => criarNaAgenda("prazo_interno") },
        { rotulo: "Pagamento", acao: () => criarNaAgenda("pagamento") },
      ]);
    };
  });
  p.querySelectorAll("[data-ag-mais]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const c = compromisso(b, "agMais");
      if (!c) return;
      menuNaLinha(b, [
        { icone: "edit", rotulo: "Abrir", acao: () => abrirFormAgenda(Object.assign({}, c)) },
        { icone: "content_copy", rotulo: "Copiar convite", acao: () => copiarTexto(conviteDe(c, ""), "convite copiado") },
        "-",
        { icone: "delete", rotulo: "Excluir", perigo: true, acao: () => apagarCompromisso(c) },
      ]);
    };
  });
  p.querySelectorAll("[data-ag-reuniao]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const c = compromisso(b, "agReuniao");
      if (!c) return;
      menuNaLinha(b, [
        { icone: "videocam", rotulo: "Abrir uma sala no Meet", acao: () => window.open(SALAS.meet, "_blank") },
        { icone: "videocam", rotulo: "Abrir uma sala no Teams", acao: () => window.open(SALAS.teams, "_blank") },
        "-",
        { icone: "link", rotulo: "Colar o link e montar o convite", acao: () => pedirLinkDaSala(b, c) },
      ]);
    };
  });
  p.querySelectorAll("[data-ag-sala]").forEach((b) => { b.onclick = () => window.open(SALAS[b.dataset.agSala], "_blank"); });
  p.querySelectorAll("[data-ag-abrir-tarefa]").forEach((el) => {
    el.onclick = () => {
      const t = d.tarefas.find((x) => x.id === Number(el.dataset.agAbrirTarefa));
      abrirTarefaNaAgenda(Number(el.dataset.agAbrirTarefa), ag.dia, Boolean(t && t.concluida));
    };
  });
  p.querySelectorAll("[data-ag-concluir]").forEach((el) => {
    el.onclick = (e) => {
      e.stopPropagation();
      const t = d.tarefas.find((x) => x.id === Number(el.dataset.agConcluir));
      if (t) concluirTarefa(t.id, !t.concluida);
    };
  });
  ligarEntrada(p, "[data-ag-nova-tarefa]", "[data-ag-entrada-tarefa]",
    (texto) => criarTarefa({ titulo: texto, prazo: ag.dia }));
  const nota = p.querySelector("[data-ag-nota]");
  if (nota) nota.onchange = () => {
    fetch("/api/agenda/nota", { method: "POST", headers: AG_JSON, body: JSON.stringify({ dia: ag.dia, texto: nota.value }) });
  };
}

/* Um "+ algo" que vira campo de texto ao clicar. */
function ligarEntrada(p, ligacao, entrada, criar) {
  const lig = p.querySelector(ligacao);
  const ent = p.querySelector(entrada);
  if (!lig || !ent) return;
  const campo = ent.querySelector("input");
  lig.onclick = () => { ent.hidden = false; lig.hidden = true; campo.focus(); };
  const enviar = () => { if (campo.value.trim()) criar(campo.value.trim()); };
  ent.querySelector("button").onclick = enviar;
  campo.onkeydown = (e) => {
    if (e.key === "Enter") enviar();
    if (e.key === "Escape") { ent.hidden = true; lig.hidden = false; }
  };
}

function pedirLinkDaSala(botao, c) {
  const corpo = botao.closest(".ag-corpo");
  if (!corpo || corpo.querySelector("[data-ag-link]")) return;
  const caixa = document.createElement("span");
  caixa.className = "ag-entrada";
  caixa.innerHTML = '<input type="text" data-ag-link="1" placeholder="cole o link do Meet, Zoom ou Teams"><button>Montar convite</button>';
  corpo.appendChild(caixa);
  const campo = caixa.querySelector("input");
  campo.focus();
  const montar = () => {
    const link = campo.value.trim();
    if (!/^https?:\/\//i.test(link)) { avisoCert("isso não parece um link de reunião"); return; }
    enviarConvite(c.titulo, conviteDe(c, link));
  };
  caixa.querySelector("button").onclick = montar;
  campo.onkeydown = (e) => { if (e.key === "Enter") montar(); if (e.key === "Escape") caixa.remove(); };
}

function conviteDe(c, link) {
  return "Olá," + "\n\n" +
    "Segue o convite para " + c.titulo + ", em " + diaPorExtenso(c.data) + " às " + c.hora +
    (c.duracao ? " (" + duracaoEmTexto(c.duracao) + ")" : "") + "." +
    (link ? "\n\n" + link : "") + "\n\n" + "Até lá.";
}

/* O envio sai pela conta de e-mail da pessoa e passa pela fila de aprovacao,
   como toda acao que sai da maquina. */
async function enviarConvite(assunto, corpo) {
  if (!mail.contas) {
    try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { mail.contas = null; }
  }
  if (!mail.contas || !mail.contas.contas.length) { marcarDestino("caixa"); return mostrarEmail(); }
  mail.conta = mail.contas.contas.find((x) => x.em_uso) || mail.contas.contas[0];
  marcarDestino("caixa");
  telaEscrever({ assunto: assunto, corpo: corpo });
}

function copiarTexto(texto, aviso) {
  navigator.clipboard.writeText(texto).then(
    () => avisoCert(aviso),
    () => avisoCert("não consegui copiar"));
}

/* O menu da linha, no padrão do menu das conversas: só o texto, sem ícone,
   e o item com `sub` abre a lista dele ao lado (passar o mouse ou clicar),
   com a seta. `icone` nos itens é ignorado — ficou de antes. */
function menuNaLinha(botao, itens) {
  document.querySelectorAll(".menu-conversa.menu-novo").forEach((m) => m.remove());
  const menu = document.createElement("div");
  menu.className = "menu-conversa menu-novo";
  const botaoDoItem = (it, i, prefixo) => {
    const classe = [it.perigo ? "perigo" : "", it.atual ? "atual" : ""].filter(Boolean).join(" ");
    return '<button data-' + prefixo + '="' + i + '"' + (classe ? ' class="' + classe + '"' : "") + ">" + esc(it.rotulo) +
      (it.sub ? '<span class="seta">›</span>' : "") + "</button>";
  };
  menu.innerHTML = itens.map((it, i) => it === "-" ? '<div class="menu-risco"></div>' : botaoDoItem(it, i, "i")).join("");
  /* O menu se posiciona pelo contêiner do botão (.menu-conversa é absoluto).
     Contêiner sem posição mandava o menu para fora da tela — foi o que
     acontecia no "⋯" dos cartões de Serviços. */
  const casa = botao.parentElement;
  if (getComputedStyle(casa).position === "static") casa.style.position = "relative";
  casa.appendChild(menu);
  const fecharSub = () => { const sub = menu.querySelector(".menu-sub"); if (sub) sub.remove(); };
  menu.querySelectorAll("[data-i]").forEach((b) => {
    const item = itens[Number(b.dataset.i)];
    if (item.sub) {
      const abrirSub = (e) => {
        if (e) e.stopPropagation();
        if (menu.querySelector(".menu-sub")) return;
        const sub = document.createElement("div");
        sub.className = "menu-conversa menu-sub";
        sub.style.top = (b.offsetTop - 6) + "px";
        sub.innerHTML = item.sub.map((x, k) => x === "-" ? '<div class="menu-risco"></div>' : botaoDoItem(x, k, "k")).join("");
        menu.appendChild(sub);
        // Abre do lado que tem espaço — medido contra quem corta (a área que
        // rola), e não só a janela: medir só a janela deixava a lista cortada.
        let limite = { left: 0, right: innerWidth };
        for (let el = menu.parentElement; el && el !== document.body; el = el.parentElement) {
          const estilo = getComputedStyle(el);
          if (/(auto|hidden|scroll|clip)/.test(estilo.overflowX + estilo.overflow)) { limite = el.getBoundingClientRect(); break; }
        }
        const caixa = sub.getBoundingClientRect();
        if (caixa.left < limite.left + 8) { sub.style.right = "auto"; sub.style.left = "calc(100% + 6px)"; }
        const depois = sub.getBoundingClientRect();
        if (depois.right > limite.right - 8 && caixa.left >= limite.left + 8) { sub.style.left = ""; sub.style.right = ""; }
        sub.querySelectorAll("[data-k]").forEach((x) => {
          x.onclick = (ev) => { ev.stopPropagation(); menu.remove(); item.sub[Number(x.dataset.k)].acao(); };
        });
      };
      b.onclick = abrirSub;
      b.onmouseenter = () => abrirSub();
      return;
    }
    b.onmouseenter = fecharSub;
    b.onclick = (e) => { e.stopPropagation(); menu.remove(); item.acao(); };
  });
  setTimeout(() => document.addEventListener("click", () => menu.remove(), { once: true }), 0);
}

/* ------------------------------------------------ o formulario */

function ligarFormAgenda(p) {
  const v = ag.form;
  p.querySelectorAll("[data-ag-tipo]").forEach((b) => {
    b.onclick = () => {
      const t = b.dataset.agTipo;
      if (t === v.tipo) return;
      if (t === "tarefa") {
        v.prazo = v.prazo || v.data || ag.dia;
      } else if (v.tipo === "tarefa") {
        Object.assign(v, compromissoEmBranco(t), { titulo: v.titulo, data: v.prazo || ag.dia, anotacao: v.anotacao });
      }
      v.tipo = t;
      if (t === "compromisso" && !v.onde) v.onde = "online";
      desenharPainel();
    };
  });
  p.querySelectorAll("[data-ag-onde]").forEach((b) => {
    b.onclick = () => {
      v.onde = b.dataset.agOnde;
      p.querySelectorAll("[data-ag-onde]").forEach((x) => x.classList.toggle("on", x === b));
    };
  });
  p.querySelectorAll("[data-c]").forEach((el) => {
    const guardar = () => {
      v[el.dataset.c] = el.dataset.c === "cadastro_id" ? (Number(el.value) || null) : el.value;
    };
    el.oninput = guardar;
    el.onchange = () => { guardar(); if (el.dataset.c === "data" || el.dataset.c === "duracao") carregarLivres(p); };
    if (el.tagName === "INPUT") el.onkeydown = (e) => { if (e.key === "Enter") { guardar(); salvarFormAgenda(); } };
  });
  const convite = p.querySelector("[data-ag-convite]");
  if (convite) convite.onclick = () => { v.convite = !v.convite; convite.classList.toggle("on", v.convite); };
  p.querySelector("[data-ag-salvar]").onclick = salvarFormAgenda;
  const apagar = p.querySelector("[data-ag-apagar]");
  if (apagar) apagar.onclick = () => (v.tipo === "tarefa" ? apagarTarefa(v.id) : apagarCompromisso(v));
  const titulo = p.querySelector('[data-c="titulo"]');
  if (titulo && !v.titulo) titulo.focus();
  if (v.tipo !== "tarefa") carregarLivres(p);
}

/* Os horarios em que cabe: o que era a tela de Agendamento. */
async function carregarLivres(p) {
  const alvo = p.querySelector("[data-ag-livres]");
  if (!alvo) return;
  const v = ag.form;
  if (!v.data) { alvo.innerHTML = '<span class="ag-vazio-chip">escolha a data</span>'; return; }
  alvo.innerHTML = '<span class="ag-vazio-chip">procurando…</span>';
  let d;
  try {
    d = await (await fetch("/api/agenda/livres?dia=" + v.data + "&duracao=" + (Number(v.duracao) || 60))).json();
  } catch (err) {
    alvo.innerHTML = "";
    return;
  }
  if (!d.horarios.length) {
    alvo.innerHTML = '<span class="ag-vazio-chip">nenhum horário livre neste dia com essa duração</span>';
    return;
  }
  alvo.innerHTML = d.horarios.slice(0, 8).map((h) => {
    const classe = h === v.hora ? "on" : "";
    return '<button class="' + classe + '" data-ag-livre="' + h + '">' + h + "</button>";
  }).join("");
  alvo.querySelectorAll("[data-ag-livre]").forEach((b) => {
    b.onclick = () => {
      v.hora = b.dataset.agLivre;
      const campo = p.querySelector('[data-c="hora"]');
      if (campo) campo.value = v.hora;
      alvo.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    };
  });
}

async function salvarFormAgenda() {
  const v = ag.form;
  const aviso = document.querySelector("[data-ag-aviso]");
  if (!(v.titulo || "").trim()) { aviso.textContent = "dê um título"; return; }
  try {
    if (v.tipo === "tarefa") {
      const r = await fetch("/api/tarefas", {
        method: "POST", headers: AG_JSON,
        body: JSON.stringify({ id: v.id || null, dados: {
          titulo: v.titulo.trim(), prazo: v.prazo || "", lista: (v.lista || "").trim(),
          cadastro_id: v.cadastro_id || null, anotacao: v.anotacao || "",
        } }),
      });
      if (!r.ok) throw new Error(await erroDe(r));
      const t = await r.json();
      ag.form = null;
      if (ag.visao === "tarefas") {
        ag.tar.aberta = t.id;
        ag.painel = "tarefa";
      } else {
        ag.painel = "dia";
        ag.diaAberto = null;
        avisoCert("tarefa criada" + (t.prazo ? " para " + dataCurta(t.prazo) : ""));
      }
      return mostrarAgenda();
    }

    const dados = {
      titulo: v.titulo.trim(), tipo: v.tipo, data: v.data, hora: v.hora || "09:00",
      duracao: Number(v.duracao) || 60, onde: v.onde || "", cadastro_id: v.cadastro_id || null,
      anotacao: v.anotacao || "", avisar_min: Number(v.avisar_min) || 0,
    };
    const r = await fetch("/api/agenda", {
      method: "POST", headers: AG_JSON, body: JSON.stringify({ id: v.id || null, dados: dados }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    const c = await r.json();
    const d = deIso(dados.data);
    ag.dia = dados.data;
    ag.diaAberto = null;
    ag.mes = new Date(d.getFullYear(), d.getMonth(), 1);
    ag.semana = iso(segundaDe(d));
    ag.form = null;
    ag.painel = "dia";
    await mostrarAgenda();
    if (v.convite) enviarConvite(c.titulo, conviteDe(c, ""));
  } catch (err) {
    aviso.textContent = "não consegui salvar: " + (err.message || err);
  }
}

async function apagarCompromisso(c) {
  if (!(await confirmar({ titulo: "Excluir este compromisso?", contexto: "Agenda › " + c.titulo, texto: "Ele sai da agenda. " + LIXEIRA_TEXTO, confirmar: "Excluir", perigo: true }))) return;
  const r = await fetch("/api/agenda/" + c.id, { method: "DELETE" });
  ag.form = null;
  ag.painel = "dia";
  ag.diaAberto = null;
  mostrarAgenda();
  avisarLixeira(r, () => mostrarAgenda());
}

/* ------------------------------------------------- a ficha da tarefa */

function ligarFichaDaTarefa(p) {
  const t = ag.tar.itens.find((x) => x.id === ag.tar.aberta);
  if (!t) return;
  p.querySelectorAll("[data-ag-concluir]").forEach((el) => { el.onclick = () => concluirTarefa(t.id, !t.concluida); });
  const estrela = p.querySelector("[data-ag-estrela]");
  if (estrela) estrela.onclick = () => marcarImportante(t.id, !t.importante);
  const fechar = p.querySelector("[data-ag-fechar-tarefa]");
  if (fechar) fechar.onclick = () => { ag.tar.aberta = null; desenharAgenda(); };

  p.querySelectorAll("[data-ag-etapa]").forEach((el) => {
    el.onclick = async () => {
      const e = t.etapas.find((x) => x.id === Number(el.dataset.agEtapa));
      if (!e) return;
      await fetch("/api/etapas/" + e.id, { method: "POST", headers: AG_JSON, body: JSON.stringify({ valor: !e.feita }) });
      recarregarAgenda();
    };
  });
  ligarEntrada(p, "[data-ag-nova-etapa]", "[data-ag-entrada-etapa]", async (texto) => {
    await fetch("/api/tarefas/" + t.id + "/etapas", { method: "POST", headers: AG_JSON, body: JSON.stringify({ titulo: texto }) });
    recarregarAgenda();
  });
  const meuDia = p.querySelector("[data-ag-meu-dia]");
  if (meuDia) meuDia.onclick = async () => {
    await fetch("/api/tarefas/" + t.id + "/meu-dia", { method: "POST", headers: AG_JSON, body: JSON.stringify({ valor: !t.meu_dia }) });
    recarregarAgenda();
  };
  p.querySelectorAll("[data-ag-campo]").forEach((el) => {
    el.onchange = () => {
      const c = el.dataset.agCampo;
      salvarCamposDaTarefa(t, { [c]: c === "cadastro_id" ? (Number(el.value) || null) : el.value });
    };
  });
  const ligar = p.querySelector("[data-ag-ligar]");
  if (ligar) ligar.onclick = () => escolherDocumentoParaTarefa(t.id);
  const cad = p.querySelector("[data-ag-cadastro]");
  if (cad) cad.onclick = () => { marcarDestino("cadastros"); mostrarCadastros(); };
  const verDia = p.querySelector("[data-ag-ver-dia]");
  if (verDia) verDia.onclick = () => {
    ag.dia = verDia.dataset.agVerDia;
    const d = deIso(ag.dia);
    ag.mes = new Date(d.getFullYear(), d.getMonth(), 1);
    ag.diaAberto = null;
    mostrarAgenda("mes");
  };
  const apagar = p.querySelector("[data-ag-apagar-tarefa]");
  if (apagar) apagar.onclick = () => apagarTarefa(t.id);
  carregarVinculosDaTarefa(t.id);
}

async function criarTarefa(dados) {
  const r = await fetch("/api/tarefas", { method: "POST", headers: AG_JSON, body: JSON.stringify({ dados: dados }) });
  if (!r.ok) { avisoCert("não consegui criar: " + await erroDe(r)); return; }
  ag.diaAberto = null;
  recarregarAgenda();
}

async function concluirTarefa(id, valor) {
  const r = await fetch("/api/tarefas/" + id + "/concluir", { method: "POST", headers: AG_JSON, body: JSON.stringify({ valor: valor }) });
  if (r.ok) {
    const d = await r.json();
    if (d.aviso_repeticao) avisoCert("essa tarefa repete — " + d.aviso_repeticao);
  }
  ag.diaAberto = null;
  recarregarAgenda();
}

async function marcarImportante(id, valor) {
  await fetch("/api/tarefas/" + id + "/importante", { method: "POST", headers: AG_JSON, body: JSON.stringify({ valor: valor }) });
  recarregarAgenda();
}

async function salvarCamposDaTarefa(t, mudancas) {
  const dados = Object.assign({
    titulo: t.titulo, importante: t.importante, prazo: t.prazo || "", lembrar_em: t.lembrar_em || "",
    repetir: t.repetir || "", lista: t.lista || "", cadastro_id: t.cadastro_id || null, anotacao: t.anotacao || "",
  }, mudancas);
  const r = await fetch("/api/tarefas", { method: "POST", headers: AG_JSON, body: JSON.stringify({ id: t.id, dados: dados }) });
  if (!r.ok) { avisoCert("não consegui salvar: " + await erroDe(r)); return; }
  recarregarAgenda();
}

function apagarTarefasEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/tarefas/" + id, {
    rotulo: "tarefa", contexto: "Agenda › Tarefas", texto: "Saem da lista, com as etapas.",
    depois: () => { ag.tar.escolhidas.clear(); ag.tar.aberta = null; ag.form = null; recarregarAgenda(); },
  });
}

async function concluirTarefasEmLote(ids) {
  for (const id of ids) await concluirTarefa(Number(id), true);
  ag.tar.escolhidas.clear();
  avisoCert(plural(ids.length, "tarefa") + (ids.length === 1 ? " concluída" : " concluídas"), { tom: "ok" });
  recarregarAgenda();
}

async function apagarTarefa(id) {
  const t = ag.tar.itens.find((x) => x.id === id) || ag.form || {};
  if (!(await confirmar({ titulo: "Excluir esta tarefa?", contexto: "Agenda › " + (t.titulo || "tarefa"), texto: "Ela sai da lista, com as etapas. " + LIXEIRA_TEXTO, confirmar: "Excluir", perigo: true }))) return;
  const r = await fetch("/api/tarefas/" + id, { method: "DELETE" });
  ag.tar.aberta = null;
  ag.form = null;
  ag.painel = ag.visao === "tarefas" ? "tarefa" : "dia";
  ag.diaAberto = null;
  recarregarAgenda();
  avisarLixeira(r, () => recarregarAgenda());
}

/* O vinculo e pelo conteudo do arquivo: renomear ou mover nao quebra. */
async function carregarVinculosDaTarefa(id) {
  const alvo = document.querySelector("[data-ag-vinculos]");
  if (!alvo) return;
  let d;
  try {
    d = await (await fetch("/api/tarefas/" + id + "/vinculos")).json();
  } catch (err) {
    alvo.innerHTML = "";
    return;
  }
  alvo.innerHTML = d.vinculos.length
    ? d.vinculos.map((v) =>
        '<div class="ag-ligado">' + glifo(v.nome) + "<span>" + esc(v.nome) + "</span>" +
        (v.existe ? '<button data-ag-abrir-doc="' + esc(v.caminho) + '">abrir</button>' : '<small class="contagem">fora do acervo</small>') +
        '<button class="ag-tirar" data-ag-tirar="' + v.id + '" title="Desligar">' + ic("close", 16) + "</button></div>").join("")
    : "<p>Nenhum documento ligado ainda.</p>";
  alvo.querySelectorAll("[data-ag-abrir-doc]").forEach((b) => {
    b.onclick = () => fetch("/api/biblioteca/abrir-pasta", { method: "POST", headers: AG_JSON, body: JSON.stringify({ caminho: b.dataset.agAbrirDoc }) });
  });
  alvo.querySelectorAll("[data-ag-tirar]").forEach((b) => {
    b.onclick = async () => {
      await fetch("/api/vinculos/" + b.dataset.agTirar, { method: "DELETE" });
      carregarVinculosDaTarefa(id);
    };
  });
}

async function escolherDocumentoParaTarefa(id) {
  const alvo = document.querySelector("[data-ag-vinculos]");
  if (!alvo) return;
  alvo.innerHTML = "<p>lendo o acervo…</p>";
  let d;
  try {
    d = await (await fetch("/api/biblioteca")).json();
  } catch (err) {
    alvo.innerHTML = "<p>não consegui ler o acervo.</p>";
    return;
  }
  alvo.innerHTML = '<div class="ag-escolher">' +
    (d.documentos.length
      ? d.documentos.slice(0, 40).map((x) =>
          '<div class="ag-ligado">' + glifo(x.nome) + "<span>" + esc(x.nome) + '</span><button data-ag-liga="' + esc(x.sha1) +
          '" data-nome="' + esc(x.nome) + '">Ligar</button></div>').join("")
      : "<p>O acervo está vazio.</p>") + "</div>";
  alvo.querySelectorAll("[data-ag-liga]").forEach((b) => {
    b.onclick = async () => {
      await fetch("/api/tarefas/" + id + "/vincular", {
        method: "POST", headers: AG_JSON, body: JSON.stringify({ sha1: b.dataset.agLiga, nome: b.dataset.nome }),
      });
      carregarVinculosDaTarefa(id);
    };
  });
}

/* ---------------------------------------------- prazos dos documentos */

async function abrirSugestoes() {
  let s;
  try {
    s = (await (await fetch("/api/tarefas/sugestoes")).json()).sugestoes;
  } catch (err) {
    avisoCert("não consegui ler os documentos");
    return;
  }
  ag.sugestoes = s;
  ag.form = null;
  ag.painel = "sugestoes";
  desenharPainel();
}

function ligarSugestoes(p) {
  p.querySelectorAll("[data-ag-aceitar]").forEach((b) => {
    b.onclick = async () => {
      const x = ag.sugestoes[Number(b.dataset.agAceitar)];
      const r = await fetch("/api/tarefas", {
        method: "POST", headers: AG_JSON,
        body: JSON.stringify({ dados: { titulo: x.titulo, prazo: x.prazo, lista: x.lista } }),
      });
      if (!r.ok) { avisoCert("não consegui criar: " + await erroDe(r)); return; }
      b.disabled = true;
      b.textContent = "criada";
      ag.diaAberto = null;
      try { await carregarAgenda(); } catch (err) { return; }
      tituloDaAgenda();
    };
  });
}

