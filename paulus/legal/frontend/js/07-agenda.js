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
  tar: { filtro: "meu_dia", lista: "", itens: [], compromissos: [], contagens: {}, listas: [],
         clientes: [], repeticoes: [], aberta: null, aberto: null, escolhidas: new Set() },
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
/* COMPROMISSO E TAREFA. Compromisso é o que se agenda — reunião,
   videoconferência, audiência —, com hora, duração e lugar. Tarefa é o do
   dia a dia (inclusive prazo interno e pagamento), com prazo e, se quiser,
   uma hora. Na grade, a tarefa aberta é o gênero "prazo" e a feita, "tarefa". */
const NOME_DO_TIPO = {
  compromisso: ["Novo compromisso", "Editar compromisso"],
  tarefa: ["Nova tarefa", "Editar tarefa"],
};
const LEGENDA_DA_AGENDA = {
  compromisso: "Compromisso", prazo: "Tarefa", pedido: "Pedido pelo link",
  tarefa: "Tarefa feita", documento: "Data em documento", pagamento: "Pagamento",
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
  if (s === "hoje") return { texto: "hoje" + (t.hora ? " " + t.hora : ""), acc: true };
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
    ag.painel = ag.visao === "tarefas" ? "tarefa" : "dia";
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
    [["mes", "Mês"], ["semana", "Semana"], ["tarefas", "To-do"]].map(([v, r]) => {
      const classe = v === ag.visao ? "ativa" : "";
      return '<button class="' + classe + '" data-visao="' + v + '">' + r + "</button>";
    }).join("") + "</div>" +
    '<button class="com-icone" data-ag-novo="compromisso">' + ic("event", 16) + "Adicionar compromisso</button>" +
    '<button class="primario com-icone" data-ag-novo="tarefa">' + ic("task_alt", 16) + "Adicionar tarefa</button>";
  $("acoes-tela").querySelectorAll("[data-visao]").forEach((b) => { b.onclick = () => mostrarAgenda(b.dataset.visao); });
  // Os dois do pop-up do dia sao os dois daqui: um menu para duas coisas era
  // um clique a mais para dizer o que ja cabia escrito.
  $("acoes-tela").querySelectorAll("[data-ag-novo]").forEach((b) => {
    b.onclick = () => criarNaAgenda(b.dataset.agNovo);
  });
}

function tituloDaAgenda() {
  const c = ag.tar.contagens || {};
  let titulo, meta;
  if (ag.visao === "mes") {
    titulo = "Agenda";
    const n = (ag.grade && ag.grade.contagem) || {};
    meta = plural(n.compromissos || 0, "compromisso") + " · " + plural(c.abertas || 0, "tarefa aberta", "tarefas abertas");
  } else if (ag.visao === "semana") {
    const seg = deIso(ag.semana), dom = andarDias(seg, 6);
    titulo = "Agenda";
    meta = "Semana de " + seg.getDate() +
      (seg.getMonth() !== dom.getMonth() ? " de " + MESES_NOME[seg.getMonth()] : "") +
      " a " + dom.getDate() + " de " + MESES_NOME[dom.getMonth()];
    const cs = (ag.grade && ag.grade.compromissos) || [];
    meta = plural(cs.length, "compromisso") + " · " + plural((ag.grade && ag.grade.contagem.prazos) || 0, "tarefa aberta", "tarefas abertas");
  } else {
    const f = FILTROS_TAREFA.find((x) => x.id === ag.tar.filtro);
    titulo = "Agenda";
    const abertas = ag.tar.itens.filter((t) => !t.concluida).length;
    const comps = ag.tar.lista ? 0 : (ag.tar.compromissos || []).length;
    meta = (ag.tar.lista || (f ? f.rotulo : "Tarefas")) + " · " + plural(abertas, "tarefa") +
      (comps ? " · " + plural(comps, "compromisso") : "") +
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

/* Cada coisa na sua visão: a tarefa leva a Tarefas (com a data do dia), e o
   compromisso leva à Semana - a agenda de horários -, com o formulário. */
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
    Object.assign(ag.tar, { itens: d.tarefas, compromissos: d.compromissos || [], contagens: d.contagens, listas: d.listas,
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
  const painel = painelDaAgenda();
  const classe = "acervo agenda" + (painel ? "" : " sem-painel");
  $("centro").innerHTML = '<div class="' + classe + '" id="agenda"><div class="acervo-principal">' +
    principal + "</div>" + painel + "</div>";
  ligarAgenda();
  // A entrada e do assunto: outra visao, outro filtro, outra lista. Concluir
  // uma tarefa tambem redesenha, e ali a tela nao pode piscar.
  if (conteudoNovo("agenda:" + ag.visao + ":" + ag.zoom + ":" + ag.tar.filtro + ":" + ag.tar.lista)) {
    entraConteudo($("centro").firstElementChild);
    entraLista($("centro"), ".ag-linha, .ag-cel, .ag-semana-dia");
  }
  // No Mês e na Semana o formulário é um pop-up: quem chega com ele pedido
  // (Agendar em Cadastros, a gravação, a troca para a Semana) o encontra aberto.
  if (ag.painel === "form" && ag.form && !document.getElementById("ag-form-pop")) abrirFormNoPopup();
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
  html += "</div>" + legendaDaAgenda(["compromisso", "prazo", "tarefa", "documento"],
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
/* A SEMANA NO MESMO DESENHO DO MÊS. Os sete dias, com o número num círculo
   (hoje com o fio de destaque, o dia escolhido cheio) - clicar escolhe o dia
   e o painel mostra tudo dele. Embaixo, as horas com um fio fino, sem a
   grade pesada; o que tem hora vira um bloco com o ponto do tipo, como no
   mês. O que cai fora das 7 às 20 aparece numa faixa abaixo. */
function vistaSemanaAgenda() {
  const seg = deIso(ag.semana);
  const hoje = iso(new Date());
  const g = ag.grade;
  const dias = [0, 1, 2, 3, 4, 5, 6].map((i) => andarDias(seg, i));

  const cabeca = '<div class="ag-semana-dias"><span></span>' + dias.map((d) => {
    const k = iso(d);
    const fds = d.getDay() === 0 || d.getDay() === 6;
    const classe = "ag-semana-dia" + (fds ? " ag-fds" : "") + (k === hoje ? " ag-hoje" : "") + (k === ag.dia ? " ag-escolhido" : "");
    return '<span class="' + classe + '" data-ag-dia="' + k + '"><small>' + DIAS_CURTOS[(d.getDay() + 6) % 7] + "</small><b>" + d.getDate() + "</b></span>";
  }).join("") + "</div>";

  const semHora = dias.map((d) => (g.dias[iso(d)] || []).filter((x) => !x.hora));
  let diaTodo = "";
  if (semHora.some((l) => l.length)) {
    diaTodo = '<div class="ag-dia-todo"><div class="ag-rotulo-hora">dia todo</div>' + dias.map((d, i) => {
      const k = iso(d);
      return "<div>" + semHora[i].map((x) => blocoDaSemana(x, k)).join("") + "</div>";
    }).join("") + "</div>";
  }

  let grade = '<div class="ag-rolagem"><div class="ag-semana">';
  for (let h = HORA_INICIO; h <= HORA_FIM; h++) {
    grade += '<div class="ag-rotulo-hora">' + String(h).padStart(2, "0") + ":00</div>";
    dias.forEach((d) => {
      const k = iso(d);
      const fds = d.getDay() === 0 || d.getDay() === 6;
      const naHora = (g.dias[k] || []).filter((x) => x.hora && Number(x.hora.split(":")[0]) === h);
      const classe = "ag-hora-cel" + (fds ? " ag-fds" : "");
      grade += '<div class="' + classe + '" data-ag-hora="' + k + "T" + String(h).padStart(2, "0") + ':00">' +
        naHora.map((x) => blocoDaSemana(x, k)).join("") + "</div>";
    });
  }
  grade += "</div></div>";

  const resto = [];
  dias.forEach((d) => {
    const k = iso(d);
    (g.dias[k] || []).filter((x) => x.hora && (Number(x.hora.split(":")[0]) < HORA_INICIO ||
      Number(x.hora.split(":")[0]) > HORA_FIM)).forEach((x) => resto.push({ item: x, dia: k }));
  });
  const fora = resto.length
    ? '<div class="ag-fora-da-grade"><b>Fora das 7h às 20h</b>' + resto.map((r) => {
        const chave = chaveDoItem(r.item);
        ag.itens[chave] = r;
        return '<span data-ag-item="' + esc(chave) + '">' + esc(diaCurto(r.dia)) +
          (r.item.hora ? " " + r.item.hora : "") + " · " + esc(r.item.titulo) + "</span>";
      }).join("") + "</div>"
    : "";

  const dom = andarDias(seg, 6);
  const tituloSemana = seg.getDate() + (seg.getMonth() !== dom.getMonth() ? " " + MESES_NOME[seg.getMonth()].slice(0, 3) : "") +
    " – " + dom.getDate() + " " + MESES_NOME[dom.getMonth()].slice(0, 3) + " " + dom.getFullYear();
  return '<div class="ag-cartao ag-calendario ag-cartao-semana">' + topoDoCalendario(tituloSemana) + cabeca + diaTodo + grade + fora +
    legendaDaAgenda(["compromisso", "prazo", "tarefa", "documento"], "Clique no dia para ver · clique numa hora vazia para marcar") + "</div>";
}

function blocoDaSemana(x, dia) {
  const chave = chaveDoItem(x);
  ag.itens[chave] = { item: x, dia: dia };
  const genero = generoDaMarca(x);
  const classe = "ag-bloco ag-" + genero;
  const ponto = "ag-ponto ag-" + genero;
  const rotulo = x.hora || { prazo: "tarefa", tarefa: "feita", documento: "documento" }[genero] || "";
  return '<div class="' + classe + '" data-ag-item="' + esc(chave) + '" title="' + esc((x.hora ? x.hora + " " : "") + x.titulo) + '">' +
    '<small><i class="' + ponto + '"></i>' + esc(rotulo) + "</small><span>" + esc(x.titulo) + "</span></div>";
}

/* -------------------------------------------------------- as tarefas */

function vistaTarefas() {
  const c = ag.tar.contagens || {};
  const listas = ag.tar.listas.slice();
  if (ag.tar.lista && !listas.some((l) => l.nome === ag.tar.lista)) listas.push({ nome: ag.tar.lista, abertas: 0 });

  const somaComps = { meu_dia: c.compromissos_hoje || 0, planejadas: c.compromissos_planejados || 0 };
  const filtros = FILTROS_TAREFA.map((f) => {
    const classe = "ag-lista-item" + (!ag.tar.lista && f.id === ag.tar.filtro ? " ativa" : "");
    return '<button class="' + classe + '" data-ag-filtro="' + f.id + '"><span class="ag-nome">' + f.rotulo + "</span>" +
      (f.id === "concluidas" ? "" : contaDaLista((c[f.id] || 0) + (somaComps[f.id] || 0), f.id === "importante")) + "</button>";
  });
  /* "Atribuidas a mim" pede equipe, que so existe quando Cadastros tiver. */
  filtros.splice(3, 0, '<button class="ag-lista-item adiante" data-ag-adiante="1" title="Quando houver equipe em Cadastros">' +
    '<span class="ag-nome">Atribuídas a mim</span></button>');

  const esquerda = '<div class="ag-listas">' + filtros.join("") +
    '<span class="ac-divisa"></span><span class="ac-secao">Minhas listas</span>' +
    (listas.length
      ? listas.map((l, i) => {
          const classe = "ag-lista-item" + (l.nome === ag.tar.lista ? " ativa" : "");
          return '<button class="' + classe + '" data-ag-lista="' + esc(l.nome) + '" title="' + esc(l.nome) + '">' + corDaLista(i) +
            '<span class="ag-nome">' + esc(l.nome) + "</span>" + contaDaLista(l.abertas || 0, false) + "</button>";
        }).join("")
      : '<span class="ac-secao">nenhuma ainda</span>') +
    '<button class="ac-incluir" data-ag-nova-lista="1">' + ic("add", 16) + "Nova lista</button></div>";

  const abertas = ag.tar.itens.filter((t) => !t.concluida);
  const feitas = ag.tar.itens.filter((t) => t.concluida);
  const comps = ag.tar.lista ? [] : (ag.tar.compromissos || []);
  const prazoSugerido = ag.tar.filtro === "meu_dia" || ag.tar.filtro === "importante" ? iso(new Date()) : "";
  let corpo;
  if (!ag.tar.itens.length && !comps.length) {
    corpo = '<div class="ag-vazio"><h4>' + (ag.tar.filtro === "meu_dia" && !ag.tar.lista ? "Nada pendente para hoje" : "Nada aqui") + "</h4><p>" +
      (ag.tar.filtro === "meu_dia" && !ag.tar.lista
        ? "Os compromissos de hoje, o que tem prazo para hoje, o que já venceu e o que você trouxe para o dia aparecem nesta lista."
        : ag.tar.filtro === "planejadas" && !ag.tar.lista
          ? "Nenhum compromisso nem tarefa com data daqui para a frente."
          : "Nenhuma tarefa " + (ag.tar.lista ? "nesta lista" : "neste filtro") + " ainda.") + "</p></div>";
  } else {
    corpo = linhasDoPeriodo(abertas, comps) +
      (feitas.length ? '<div class="ag-secao">Concluídas · ' + feitas.length + "</div>" + feitas.map(linhaDaTarefa).join("") : "");
  }
  // Tarefa e compromisso nascem no pop-up (o Novo, em cima): a caixa de
  // adicionar da lista saiu. A barra de cima diz o que a lista tem.
  const f = FILTROS_TAREFA.find((x) => x.id === ag.tar.filtro);
  const nAbertas = abertas.length + comps.length;
  const direita = '<div class="ag-cartao">' +
    '<div class="tabela-barra"><b>Tarefas e compromissos</b><span class="nota-barra">' +
    esc(ag.tar.lista || (f ? f.rotulo : "Tarefas")) + " · " +
    (ag.tar.filtro === "concluidas" ? plural(feitas.length, "concluída") : plural(nAbertas, "item", "itens")) + "</span>" +
    '<span class="direita"><button data-ag-sugestoes="1" title="Datas que o assistente leu nos contratos abertos">' +
    ic("auto_awesome", 16) + "Prazos lidos nos documentos</button></span></div>" +
    (ag.tar.escolhidas.size
      ? '<div class="barra-selecao ag-selecao">' + barraDeSelecao(ag.tar.escolhidas.size, true,
        '<button data-ag-sel-concluir="1">' + ic("task_alt", 16) + "Concluir</button><span class=\"divisa-v\"></span>" +
        '<button class="botao-icone perigo" data-ag-sel-apagar="1" title="Excluir" aria-label="Excluir">' + ic("delete", 18) + "</button>", "data-ag-sel-limpar") + "</div>"
      : "") +
    '<div class="tabela-corpo">' + corpo + "</div></div>";

  return '<div class="ag-tarefas">' + esquerda + direita + "</div>";
}

/* Tarefas e compromissos numa lista só, na ordem do dia e da hora. A tarefa
   sem prazo (trazida para Meu dia) conta como de hoje e vai depois do que tem
   hora; a atrasada vem antes. Em Planejadas, cada dia ganha o cabeçalho dele.
   Em Importante e nas listas não há compromisso, e a ordem é a das tarefas. */
function linhasDoPeriodo(abertas, comps) {
  const hoje = iso(new Date());
  const porDia = ag.tar.filtro === "planejadas" && !ag.tar.lista;
  if (!comps.length && !porDia) return abertas.map(linhaDaTarefa).join("");
  const itens = abertas.map((t) => ({ dia: t.prazo || hoje, hora: t.hora || "99", html: linhaDaTarefa(t) }))
    .concat(comps.map((k) => ({ dia: k.data, hora: k.hora || "99", html: linhaDoCompromisso(k) })));
  itens.sort((a, b) => (a.dia + a.hora).localeCompare(b.dia + b.hora));
  if (!porDia) return itens.map((x) => x.html).join("");
  const amanha = iso(andarDias(new Date(), 1));
  let dia = "";
  return itens.map((x) => {
    const cabeca = x.dia !== dia ? '<div class="ag-secao">' + (x.dia === amanha ? "Amanhã" : maiuscula(diaCurto(x.dia))) + "</div>" : "";
    dia = x.dia;
    return cabeca + x.html;
  }).join("");
}

/* O compromisso na lista: a agenda no lugar da marca de concluir, a hora, o
   lugar e com quem. O que já acabou hoje fica apagado. Clicar abre a exibição. */
function linhaDoCompromisso(k) {
  const agora = new Date();
  const hoje = iso(agora);
  const hhmm = String(agora.getHours()).padStart(2, "0") + ":" + String(agora.getMinutes()).padStart(2, "0");
  const passou = k.data === hoje && (k.fim || k.hora) < hhmm;
  const quando = (k.data === hoje ? "hoje " : "") + k.hora + (k.fim ? "–" + k.fim : "");
  const pecas = ['<span class="' + (passou ? "" : "ag-comp-quando") + '">' + esc(quando) + "</span>"];
  if (k.onde_rotulo) pecas.push("<span>" + esc(k.onde_rotulo) + "</span>");
  if (k.cadastro_nome) pecas.push("<span>" + esc(k.cadastro_nome) + "</span>");
  const aberto = ag.tar.aberto === k.id;
  return '<div class="ag-linha ag-linha-comp' + (passou ? " ag-passou" : "") + (aberto ? " aberta" : "") +
    '" data-ag-comp="' + k.id + '" title="Compromisso">' +
    '<span class="ag-comp-marca">' + ic("event", 18) + "</span>" +
    '<span class="ag-texto"><b>' + esc(k.titulo) + "</b><small>" + pecas.join("") + "</small></span>" +
    setaDaLinha(aberto) + "</div>" + (aberto ? fichaDoCompromissoNaLinha(k) : "");
}

function contaDaLista(n, acc) {
  const classe = "ag-conta" + (acc && n ? " ag-acc" : "");
  return '<span class="' + classe + '">' + n + "</span>";
}

function corDaLista(i) {
  const classe = "ag-cor ag-c" + (i % 4);
  return '<i class="' + classe + '"></i>';
}

/* A LINHA QUE SE ABRE (como a da gravacao, que revela o tocador). Clicar
   numa tarefa ou num compromisso abre, debaixo da linha, tudo o que antes
   morava na coluna da direita - por isso a coluna acabou. */
function linhaDaTarefa(t) {
  const aberta = ag.tar.aberta === t.id;
  if (t.concluida) {
    const classeFeita = "ag-linha ag-feita" + (aberta ? " aberta" : "") + (ag.tar.escolhidas.has(String(t.id)) ? " escolhida" : "");
    return '<div class="' + classeFeita + '" data-ag-tarefa="' + t.id + '" data-sel="' + t.id + '">' +
      '<span class="ic ic-18 ag-feita-ic" data-ag-concluir="' + t.id + '" title="Reabrir">check_circle</span>' +
      '<span class="ag-texto"><b>' + esc(t.titulo) + "</b></span>" + setaDaLinha(aberta) + "</div>" +
      (aberta ? fichaDaTarefaNaLinha(t) : "");
  }
  const classe = "ag-linha" + (aberta ? " aberta" : "") + (ag.tar.escolhidas.has(String(t.id)) ? " escolhida" : "");
  return '<div class="' + classe + '" data-ag-tarefa="' + t.id + '" data-sel="' + t.id + '">' +
    '<span class="ag-circulo ag-grande" data-ag-concluir="' + t.id + '" title="Concluir"></span>' +
    '<span class="ag-texto"><b>' + esc(t.titulo) + "</b><small>" + metaDaTarefa(t) + "</small></span>" +
    botaoEstrela(t) + setaDaLinha(aberta) + "</div>" +
    (aberta ? fichaDaTarefaNaLinha(t) : "");
}

function setaDaLinha(aberta) {
  return '<span class="ag-seta-linha' + (aberta ? " aberta" : "") + '">' + ic("expand_more", 18) + "</span>";
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

/* Mês e Semana não têm coluna: o dia e o compromisso abrem num pop-up. A
   coluna só aparece com os prazos lidos nos documentos, e na visão Tarefas,
   com a ficha da tarefa. O cadastro (novo ou editar) é sempre pop-up. */
function painelDaAgenda() {
  return "";
}

/* O painel da Agenda tem a largura dele: a alça de alargar saiu. */
function alcaDoPainel() {
  return "";
}

/* O DIA NUM POP-UP. Clicar num dia do mês ou da semana abre o que há nele
   - compromissos e tarefas numa lista só, em ordem de hora -, com Adicionar
   compromisso e Adicionar tarefa, e o botão de abrir o dia na outra visão da
   Agenda. */
function conteudoDoDia(d) {
  const titulo = maiuscula(diaPorExtenso(d.dia));
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
    // A linha abre a exibição do compromisso: as ações (sala, convite,
    // editar) moram nela, e não na lista.
    return { hora: c.hora || "", html: '<div class="' + classe + ' ag-linha-ver" data-ag-ver="' + c.id + '"><span class="ag-hora">' + esc(c.hora) +
      '</span><span class="ag-corpo"><span>' + (genero === "prazo" ? "Prazo: " : "") + esc(c.titulo) + "</span><small>" + esc(detalhe) + "</small></span>" +
      ic("chevron_right", 18) + "</div>" };
  });

  // A tarefa entra na mesma lista: no lugar da hora, a marca de concluir.
  const tarefas = d.tarefas.map((t) => {
    const classe = "ag-hora-linha ag-tarefa ag-tarefa-dia" + (t.concluida ? " ag-feita" : "");
    const detalhe = [t.hora ? t.hora : "", "tarefa", t.lista, t.cadastro_nome, t.importante && !t.concluida ? "importante" : ""].filter(Boolean).join(" · ");
    return { hora: t.hora || "", html: '<div class="' + classe + '" data-ag-abrir-tarefa="' + t.id + '"><span class="ag-hora">' +
      (t.concluida
        ? '<span class="ic ic-18 ag-feita-ic" data-ag-concluir="' + t.id + '" title="Reabrir">check_circle</span>'
        : '<span class="ag-circulo" data-ag-concluir="' + t.id + '" title="Concluir"></span>') +
      '</span><span class="ag-corpo"><span>' + esc(t.titulo) + "</span><small>" + esc(detalhe) + "</small></span></div>" };
  });
  // Tudo numa lista: o que tem hora (compromisso ou tarefa) em ordem, e as
  // tarefas sem hora depois.
  const comHora = linhas.concat(tarefas.filter((x) => x.hora)).sort((a, b) => a.hora.localeCompare(b.hora));
  const doDia = comHora.concat(tarefas.filter((x) => !x.hora));

  return {
    titulo: titulo,
    meta: meta + (comAviso ? " · " + plural(comAviso, "compromisso") + " com aviso" : ""),
    html: (doDia.length ? doDia.map((x) => x.html).join('<span class="ag-risco"></span>') : '<p class="nota">Nada neste dia.</p>') +
      '<div class="ag-adicionar-dia"><button class="com-icone" data-ag-marcar="1">' + ic("event", 16) + "Adicionar compromisso</button>" +
      '<button class="com-icone" data-ag-ir-tarefas="1">' + ic("task_alt", 16) + "Adicionar tarefa</button></div>",
  };
}

async function abrirDiaNoPopup() {
  const d = ag.diaAberto;
  // O duplo clique marca um compromisso: o clique que chega depois nao
  // reabre o pop-up por cima do formulario.
  if (!d || d.dia !== ag.dia || ag.painel === "form") return;
  const x = conteudoDoDia(d);
  const outra = ag.visao === "mes" ? "Abrir na semana" : "Abrir no mês";
  const escolha = dialogo({
    titulo: x.titulo, contexto: x.meta, classe: "dialogo-ver dialogo-dia", larga: true,
    html: '<div class="ag-dia-pop" id="ag-dia-pop">' + x.html + "</div>", cancelar: "Fechar", confirmar: outra,
  });
  const caixa = document.getElementById("ag-dia-pop");
  if (caixa) {
    ligarPainelDoDia(caixa);
    // Concluir no pop-up refaz o pop-up, com a tarefa riscada.
    caixa.querySelectorAll("[data-ag-concluir]").forEach((el) => {
      el.onclick = async (e) => {
        e.stopPropagation();
        const t = d.tarefas.find((k) => k.id === Number(el.dataset.agConcluir));
        if (!t) return;
        await fetch("/api/tarefas/" + t.id + "/concluir", { method: "POST", headers: AG_JSON, body: JSON.stringify({ valor: !t.concluida }) });
        await carregarDia();
        recarregarAgenda().then(() => abrirDiaNoPopup());
      };
    });
  }
  const r = await escolha;
  if (!r || !r.ok) return;
  const alvo = deIso(ag.dia);
  if (ag.visao === "mes") { ag.semana = iso(segundaDe(alvo)); mostrarAgenda("semana"); }
  else { ag.mes = new Date(alvo.getFullYear(), alvo.getMonth(), 1); mostrarAgenda("mes"); }
}

/* O que sai do pop-up para outra coisa (o formulário, a tarefa) fecha ele antes. */
function fecharPopupDoDia() {
  if (dialogoAberto && document.getElementById("ag-dia-pop")) dialogoAberto.fechar(null);
}

/* A EXIBIÇÃO DO COMPROMISSO (pop-up de exibição, docs/ui/05): só leitura, a
   ficha com os dados e as ações que servem ao compromisso. Editar troca para
   o cadastro; excluir fica no cadastro. */
const AVISOS_ANTES = [[0, "não avisar"], [10, "10 min antes"], [30, "30 min antes"], [60, "1 h antes"], [1440, "um dia antes"]];

async function verCompromisso(c) {
  const aviso = AVISOS_ANTES.find(([m]) => m === Number(c.avisar_min || 0));
  const horario = c.hora + (c.fim ? " às " + c.fim : "") + (c.duracao ? " (" + duracaoEmTexto(c.duracao) + ")" : "");
  const salas = c.onde === "online"
    ? '<button type="button" class="com-icone" data-ag-sala="meet">' + ic("videocam", 16) + "Sala no Meet</button>" +
      '<button type="button" class="com-icone" data-ag-sala="teams">' + ic("videocam", 16) + "Sala no Teams</button>" +
      '<button type="button" class="com-icone" data-ag-link="1">' + ic("link", 16) + "Convite com link</button>"
    : "";
  const escolha = dialogo({
    titulo: c.titulo, contexto: "Agenda › " + maiuscula(diaCurto(c.data)) + " · " + c.hora,
    classe: "dialogo-ver", larga: true, cancelar: "Fechar", confirmar: "Editar",
    html: fichaDoDialogo([
      ["Quando", maiuscula(diaPorExtenso(c.data)) + ", " + horario],
      ["Onde", c.onde_rotulo || "sem local"],
      ["Com quem", c.cadastro_nome || "ninguém do cadastro"],
      ["Aviso", aviso ? aviso[1] : ""],
      c.anotacao ? ["Anotação", c.anotacao] : null,
    ]) +
      '<div class="dialogo-acoes">' + salas +
      '<button type="button" class="com-icone" data-ag-copiar="1">' + ic("content_copy", 16) + "Copiar convite</button></div>",
  });
  const dlg = document.querySelector(".dialogo-ver");
  if (dlg) {
    dlg.querySelectorAll("[data-ag-sala]").forEach((b) => { b.onclick = () => window.open(SALAS[b.dataset.agSala], "_blank"); });
    const copiar = dlg.querySelector("[data-ag-copiar]");
    if (copiar) copiar.onclick = () => copiarTexto(conviteDe(c, ""), "convite copiado");
    const link = dlg.querySelector("[data-ag-link]");
    if (link) link.onclick = () => pedirLinkDaSala(c);
  }
  const r = await escolha;
  if (r && r.ok) abrirFormAgenda(Object.assign({}, c));
}

/* O link da sala vira convite: um cadastro pequeno, no padrão. */
async function pedirLinkDaSala(c) {
  const link = await perguntar({
    titulo: "Convite com link", contexto: "Agenda › " + c.titulo,
    campo: { rotulo: "Link da reunião", placeholder: "https://meet.google.com/…", icone: "link", dica: "O link do Meet, do Zoom ou do Teams." },
    confirmar: "Montar convite",
  });
  if (!link) return;
  if (!/^https?:/i.test(link)) { avisoCert("isso não parece um link de reunião"); return; }
  enviarConvite(c.titulo, conviteDe(c, link));
}

/* O CADASTRO (pop-up de cadastro, docs/ui/05): Novo ou Editar, os campos na
   caixa do sistema, Excluir à esquerda do rodapé só ao editar, Cancelar e a
   ação à direita. Salvar com erro avisa no rodapé e não fecha. */
function abrirFormNoPopup() {
  const v = ag.form;
  const f = partesDoFormAgenda(v);
  const vez = ag.formVez = (ag.formVez || 0) + 1;
  const escolha = dialogo({
    titulo: f.titulo, contexto: f.sub, classe: "dialogo-cadastro", larga: true,
    html: '<div class="dialogo-form" id="ag-form-pop">' + f.corpo + "</div>",
    rodape: f.excluir + '<span class="dialogo-aviso" data-ag-aviso="1"></span>',
    cancelar: "Cancelar", confirmar: f.botao, aoConfirmar: salvarFormAgenda,
  });
  const caixa = document.getElementById("ag-form-pop");
  if (caixa) ligarFormAgenda(caixa.closest(".dialogo"));
  // Fechou sem salvar (Cancelar, Esc, clique fora): o formulário sai junto.
  escolha.then(() => {
    if (ag.formVez !== vez || ag.form !== v) return;
    ag.form = null;
    ag.painel = ag.visao === "tarefas" ? "tarefa" : "dia";
  });
}

/* Com o pop-up aberto, refaz o miolo nele mesmo, sem piscar. */
function redesenharFormAgenda() {
  const caixa = document.getElementById("ag-form-pop");
  if (!caixa) return abrirFormNoPopup();
  const dlg = caixa.closest(".dialogo");
  const f = partesDoFormAgenda(ag.form);
  dlg.querySelector("#dialogo-titulo").textContent = f.titulo;
  const contexto = dlg.querySelector(".dialogo-contexto");
  if (contexto) contexto.textContent = f.sub;
  dlg.querySelector('[data-dialogo="confirmar"]').textContent = f.botao;
  caixa.innerHTML = f.corpo;
  ligarFormAgenda(dlg);
}

function fecharFormNoPopup() {
  if (dialogoAberto && document.getElementById("ag-form-pop")) dialogoAberto.fechar(null);
}

function partesDoFormAgenda(v) {
  if (v.tipo === "tarefa") return partesDoFormTarefa(v);
  const novo = !v.id;
  const nomes = NOME_DO_TIPO.compromisso;
  const sub = "Agenda › " + maiuscula(diaCurto(v.data || ag.dia)) + " · " + (v.hora || "");
  const clientes = '<option value="">ninguém do cadastro</option>' +
    ag.tar.clientes.map((k) => '<option value="' + k.id + '"' + (k.id === v.cadastro_id ? " selected" : "") + ">" + esc(k.nome) + "</option>").join("");
  const campo = (rotulo, controle, id, longo) => '<div class="dialogo-campo"><label for="' + id + '">' + rotulo + "</label>" +
    '<div class="dialogo-caixa' + (longo ? " texto-longo" : "") + '">' + controle + "</div></div>";
  const duas = (a, b) => '<div class="dialogo-duas">' + a + b + "</div>";

  const duracoes = [15, 30, 45, 60, 90, 120, 180];
  if (v.duracao && duracoes.indexOf(Number(v.duracao)) < 0) duracoes.push(Number(v.duracao));
  const ondes = [["online", "Reunião online"], ["escritorio", "No escritório"], ["telefone", "Telefone"], ["", "Sem local"]].map(([o, r]) => {
    const classe = o === (v.onde || "") ? "on" : "";
    return '<button type="button" class="' + classe + '" data-ag-onde="' + o + '">' + r + "</button>";
  }).join("");
  const classeConvite = "ag-toggle" + (v.convite ? " on" : "");
  const corpo =
    campo("Título", '<input type="text" id="ag-f-titulo" data-c="titulo" value="' + esc(v.titulo || "") + '" placeholder="Renovação — Fornecedor A" autocomplete="off">', "ag-f-titulo") +
    duas(campo("Data", '<input type="date" id="ag-f-data" data-c="data" value="' + esc(v.data || "") + '">', "ag-f-data"),
      campo("Hora", '<input type="time" id="ag-f-hora" data-c="hora" value="' + esc(v.hora || "") + '">', "ag-f-hora")) +
    duas(campo("Duração", '<select id="ag-f-duracao" data-c="duracao">' +
        duracoes.sort((a, b) => a - b).map((m) => '<option value="' + m + '"' + (m === Number(v.duracao) ? " selected" : "") + ">" + duracaoEmTexto(m) + "</option>").join("") +
        "</select>", "ag-f-duracao"),
      campo("Avisar antes", '<select id="ag-f-aviso" data-c="avisar_min">' +
        AVISOS_ANTES.map(([m, r]) => '<option value="' + m + '"' + (m === Number(v.avisar_min || 0) ? " selected" : "") + ">" + r + "</option>").join("") +
        "</select>", "ag-f-aviso")) +
    campo("Com quem", '<select id="ag-f-cliente" data-c="cadastro_id">' + clientes + "</select>", "ag-f-cliente") +
    '<div class="dialogo-campo"><label>Onde</label><div class="dialogo-chips">' + ondes + "</div></div>" +
    '<div class="dialogo-campo"><label>Cabe nestes horários</label><div class="dialogo-chips" data-ag-livres="1"><span class="dialogo-dica">procurando…</span></div></div>' +
    campo("Anotação", '<textarea id="ag-f-anotacao" rows="3" data-c="anotacao" placeholder="Pauta, endereço, o que levar…">' + esc(v.anotacao || "") + "</textarea>", "ag-f-anotacao", true) +
    '<div class="dialogo-campo"><div class="' + classeConvite + '" data-ag-convite="1"><span>Enviar convite por e-mail ao salvar</span><i></i></div>' +
    '<span class="dialogo-dica">O convite sai pelo seu e-mail e passa pela tela de Aprovações antes de ser enviado.</span></div>';
  return {
    titulo: nomes[novo ? 0 : 1], sub: sub, corpo: corpo,
    excluir: novo ? "" : '<button type="button" class="dialogo-excluir" data-ag-apagar="1">Excluir</button>',
    botao: novo ? "Marcar" : "Salvar",
  };
}

function fichaDaTarefaNaLinha(t) {
  const feitas = t.etapas.filter((e) => e.feita).length;
  const q = quandoDaTarefa(t);
  const rep = ag.tar.repeticoes.length ? ag.tar.repeticoes : [{ valor: "", rotulo: "Não repete" }];
  const classePrazo = q.acc ? "ag-acc" : "";
  const classeMeuDia = "ag-ligacao" + (t.meu_dia ? "" : " ag-fraca");

  const etapas = t.etapas.map((e) => {
    const classe = "ag-tarefa-linha" + (e.feita ? " ag-feita" : "");
    return '<div class="' + classe + '" data-ag-etapa="' + e.id + '">' +
      (e.feita ? '<span class="ic ic-18 ag-feita-ic">check_circle</span>' : '<span class="ag-circulo"></span>') +
      '<span class="ag-texto">' + esc(e.titulo) + "</span></div>";
  }).join("");

  // À esquerda o que se faz (etapas, documentos, anotação); à direita o que a
  // tarefa é (quando, repete, de quem, em que lista), numa ficha estreita -
  // rótulo e valor perto um do outro, e não nas duas pontas da tela.
  const esquerda =
    blocoDaFicha("Etapas", t.etapas.length ? feitas + " de " + t.etapas.length : "nenhuma",
      etapas +
      '<button class="ag-incluir" data-ag-nova-etapa="1">' + ic("add", 16) + "Próxima etapa</button>" +
      '<span class="ag-entrada" data-ag-entrada-etapa="1" hidden><input type="text" placeholder="Próxima etapa…"><button>Acrescentar</button></span>') +
    blocoDaFicha("Ligado a", "",
      '<div data-ag-vinculos="1"><p>carregando…</p></div>' +
      '<button class="ag-incluir" data-ag-ligar="1">' + ic("attach_file", 16) + "Ligar documento</button>" +
      (t.cadastro_nome ? '<div class="ag-ligado-linha"><span>' + esc(t.cadastro_nome) + '</span><button data-ag-cadastro="1">cadastro</button></div>' : "") +
      (t.prazo ? '<div class="ag-ligado-linha"><span>Prazo no calendário · ' + esc(diaCurto(t.prazo)) + '</span><button class="ag-acc" data-ag-ver-dia="' + esc(t.prazo) + '">abrir</button></div>' : "")) +
    blocoDaFicha("Anotação", "",
      '<textarea class="ag-nota" data-ag-campo="anotacao" placeholder="Escreva uma anotação…">' + esc(t.anotacao || "") + "</textarea>");

  const direita = blocoDaFicha("A tarefa", "",
    '<div class="painel-chaves">' +
    '<div class="ag-chave"><span>Meu dia</span><button class="' + classeMeuDia + '" data-ag-meu-dia="1">' + (t.meu_dia ? "já está" : "adicionar") + "</button></div>" +
    '<div class="ag-chave"><span>Lembrar-me</span><input type="time" data-ag-campo="lembrar_em" value="' + esc(t.lembrar_em || "") + '"></div>' +
    '<div class="ag-chave"><span>Prazo</span><input type="date" class="' + classePrazo + '" data-ag-campo="prazo" value="' + esc(t.prazo || "") + '"></div>' +
    '<div class="ag-chave"><span>Hora</span><input type="time" data-ag-campo="hora" value="' + esc(t.hora || "") + '" title="opcional"></div>' +
    '<div class="ag-chave"><span>Repetir</span><select data-ag-campo="repetir">' +
    rep.map((r) => '<option value="' + esc(r.valor) + '"' + ((t.repetir || "") === r.valor ? " selected" : "") + ">" + esc(r.rotulo) + "</option>").join("") + "</select></div>" +
    '<div class="ag-chave"><span>Cliente</span><select data-ag-campo="cadastro_id"><option value="">nenhum</option>' +
    ag.tar.clientes.map((k) => '<option value="' + k.id + '"' + (k.id === t.cadastro_id ? " selected" : "") + ">" + esc(k.nome) + "</option>").join("") + "</select></div>" +
    '<div class="ag-chave"><span>Lista</span><input type="text" data-ag-campo="lista" value="' + esc(t.lista || "") + '" placeholder="nenhuma"></div>' +
    "</div>");

  return '<div class="ag-linha-ficha" data-ag-ficha="' + t.id + '">' +
    '<div class="ag-ficha-col">' + esquerda + "</div>" +
    '<div class="ag-ficha-col">' + direita + "</div>" +
    '<div class="ag-ficha-rodape"><small>' + criadaHa(t.criada_em) + "</small>" +
    '<button class="ag-incluir ag-incluir-fino" data-ag-editar-tarefa="' + t.id + '">' + ic("edit", 16) + "Editar</button>" +
    '<button class="dialogo-excluir" data-ag-apagar-tarefa="1">Excluir</button></div>' +
    "</div>";
}

/* Um bloco da ficha: o titulo fino, a contagem a direita e o miolo. */
function blocoDaFicha(titulo, contagem, miolo) {
  return '<div class="ag-ficha-bloco"><div class="ag-ficha-bloco-cabeca"><span>' + titulo + "</span>" +
    (contagem ? '<span class="contagem">' + esc(contagem) + "</span>" : "") + "</div>" + miolo + "</div>";
}

/* O compromisso aberto na linha: a mesma ficha do pop-up de exibicao - so
   leitura -, com as acoes dele, Editar e Excluir. */
function fichaDoCompromissoNaLinha(k) {
  const aviso = AVISOS_ANTES.find(([m]) => m === Number(k.avisar_min || 0));
  const horario = k.hora + (k.fim ? " às " + k.fim : "") + (k.duracao ? " (" + duracaoEmTexto(k.duracao) + ")" : "");
  const salas = k.onde === "online"
    ? '<button type="button" class="com-icone" data-ag-sala="meet">' + ic("videocam", 16) + "Sala no Meet</button>" +
      '<button type="button" class="com-icone" data-ag-sala="teams">' + ic("videocam", 16) + "Sala no Teams</button>" +
      '<button type="button" class="com-icone" data-ag-link="' + k.id + '">' + ic("link", 16) + "Convite com link</button>"
    : "";
  return '<div class="ag-linha-ficha" data-ag-ficha-comp="' + k.id + '">' +
    '<div class="ag-ficha-col">' +
    blocoDaFicha("O compromisso", "", fichaDoDialogo([
      ["Quando", maiuscula(diaPorExtenso(k.data)) + ", " + horario],
      ["Onde", k.onde_rotulo || "sem local"],
      ["Com quem", k.cadastro_nome || "ninguém do cadastro"],
      ["Aviso", aviso ? aviso[1] : ""],
      k.anotacao ? ["Anotação", k.anotacao] : null,
    ])) + "</div>" +
    '<div class="ag-ficha-col">' +
    blocoDaFicha("O que dá para fazer", "", '<div class="dialogo-acoes">' + salas +
      '<button type="button" class="com-icone" data-ag-copiar="' + k.id + '">' + ic("content_copy", 16) + "Copiar convite</button></div>") + "</div>" +
    '<div class="ag-ficha-rodape"><small>' + esc(maiuscula(diaCurto(k.data))) + "</small>" +
    '<button class="ag-incluir ag-incluir-fino" data-ag-editar-comp="' + k.id + '">' + ic("edit", 16) + "Editar</button>" +
    '<button class="dialogo-excluir" data-ag-apagar-comp="' + k.id + '">Excluir</button></div>' +
    "</div>";
}

/* O CADASTRO DA TAREFA. Tarefa e compromisso nascem e se editam no pop-up;
   a linha aberta na lista mostra e age, mas nao escreve. */
function partesDoFormTarefa(v) {
  const novo = !v.id;
  const rep = ag.tar.repeticoes.length ? ag.tar.repeticoes : [{ valor: "", rotulo: "Não repete" }];
  const campo = (rotulo, controle, id, longo) => '<div class="dialogo-campo"><label for="' + id + '">' + rotulo + "</label>" +
    '<div class="dialogo-caixa' + (longo ? " texto-longo" : "") + '">' + controle + "</div></div>";
  const corpo =
    campo("Título", '<input type="text" id="ag-f-titulo" data-c="titulo" value="' + esc(v.titulo || "") + '" placeholder="Entregar o contrato revisado" autocomplete="off">', "ag-f-titulo") +
    '<div class="dialogo-duas">' +
    campo("Prazo", '<input type="date" id="ag-f-prazo" data-c="prazo" value="' + esc(v.prazo || "") + '">', "ag-f-prazo") +
    campo("Hora <small>(opcional)</small>", '<input type="time" id="ag-f-hora" data-c="hora" value="' + esc(v.hora || "") + '">', "ag-f-hora") + "</div>" +
    '<div class="dialogo-duas">' +
    campo("Lista", '<input type="text" id="ag-f-lista" data-c="lista" list="ag-listas-dl" value="' + esc(v.lista || "") + '" placeholder="nenhuma" autocomplete="off">' +
      '<datalist id="ag-listas-dl">' + ag.tar.listas.map((l) => '<option value="' + esc(l.nome) + '">').join("") + "</datalist>", "ag-f-lista") +
    campo("Repetir", '<select id="ag-f-repetir" data-c="repetir">' +
      rep.map((r) => '<option value="' + esc(r.valor) + '"' + ((v.repetir || "") === r.valor ? " selected" : "") + ">" + esc(r.rotulo) + "</option>").join("") +
      "</select>", "ag-f-repetir") + "</div>" +
    campo("Cliente", '<select id="ag-f-cliente" data-c="cadastro_id"><option value="">nenhum</option>' +
      ag.tar.clientes.map((k) => '<option value="' + k.id + '"' + (k.id === v.cadastro_id ? " selected" : "") + ">" + esc(k.nome) + "</option>").join("") +
      "</select>", "ag-f-cliente") +
    campo("Lembrar-me <small>(opcional)</small>", '<input type="time" id="ag-f-lembrar" data-c="lembrar_em" value="' + esc(v.lembrar_em || "") + '">', "ag-f-lembrar") +
    campo("Anotação", '<textarea id="ag-f-anotacao" rows="3" data-c="anotacao" placeholder="O que vale lembrar…">' + esc(v.anotacao || "") + "</textarea>", "ag-f-anotacao", true);
  return {
    titulo: NOME_DO_TIPO.tarefa[novo ? 0 : 1],
    sub: "Agenda › " + (v.prazo ? maiuscula(diaCurto(v.prazo)) + (v.hora ? " · " + v.hora : "") : "sem prazo"),
    corpo: corpo,
    excluir: novo ? "" : '<button type="button" class="dialogo-excluir" data-ag-apagar="1">Excluir</button>',
    botao: novo ? "Adicionar" : "Salvar",
  };
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
  const sugestoes = raiz.querySelector("[data-ag-sugestoes]");
  if (sugestoes) sugestoes.onclick = abrirSugestoes;
  const novaLista = raiz.querySelector("[data-ag-nova-lista]");
  if (novaLista) novaLista.onclick = async () => {
    const nome = await perguntar({ titulo: "Nova lista", contexto: "Agenda › Tarefas", campo: { rotulo: "Nome da lista", placeholder: "Prazos do trimestre", icone: "format_list_bulleted" }, confirmar: "Criar" });
    if (!nome || !nome.trim()) return;
    ag.tar.lista = nome.trim();
    ag.tar.aberta = null;
    avisoCert("a lista “" + ag.tar.lista + "” nasce com a primeira tarefa que você criar nela");
    mostrarAgenda();
  };
  ligarSelecao(raiz.querySelector(".ag-tarefas .tabela-corpo"), {
    linhas: ".ag-linha[data-sel]", escolhidos: ag.tar.escolhidas, aoMudar: desenharAgenda, apagar: (ids) => apagarTarefasEmLote(ids),
  });
  const selLimpar = raiz.querySelector("[data-ag-sel-limpar]");
  if (selLimpar) selLimpar.onclick = (e) => { e.stopPropagation(); ag.tar.escolhidas.clear(); desenharAgenda(); };
  const selApagar = raiz.querySelector("[data-ag-sel-apagar]");
  if (selApagar) selApagar.onclick = (e) => { e.stopPropagation(); apagarTarefasEmLote([...ag.tar.escolhidas]); };
  const selConcluir = raiz.querySelector("[data-ag-sel-concluir]");
  if (selConcluir) selConcluir.onclick = (e) => { e.stopPropagation(); concluirTarefasEmLote([...ag.tar.escolhidas]); };
  // A linha se abre e se fecha no lugar: a de baixo mostra tudo o que antes
  // ficava na coluna da direita.
  raiz.querySelectorAll("[data-ag-comp]").forEach((el) => {
    el.onclick = (e) => {
      if (e.target.closest(".ag-linha-ficha")) return;
      const id = Number(el.dataset.agComp);
      const abrindo = ag.tar.aberto !== id;
      ag.tar.aberto = abrindo ? id : null;
      ag.tar.aberta = null;
      desenharAgenda();
      if (abrindo) abrirEmAltura(document.querySelector(".ag-linha-ficha"));
    };
  });
  raiz.querySelectorAll("[data-ag-tarefa]").forEach((el) => {
    el.onclick = (e) => {
      if (e.target.closest(".ag-linha-ficha")) return;
      const id = Number(el.dataset.agTarefa);
      const abrindo = ag.tar.aberta !== id;
      ag.tar.aberta = abrindo ? id : null;
      ag.tar.aberto = null;
      ag.form = null;
      desenharAgenda();
      if (abrindo) abrirEmAltura(document.querySelector(".ag-linha-ficha"));
    };
  });
  // O que a ficha aberta na linha liga: as etapas, as chaves, o documento.
  const ficha = raiz.querySelector(".ag-linha-ficha[data-ag-ficha]");
  if (ficha) ligarFichaDaTarefa(ficha);
  const fichaComp = raiz.querySelector(".ag-linha-ficha[data-ag-ficha-comp]");
  if (fichaComp) ligarFichaDoCompromisso(fichaComp);
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

}

async function escolherDia(dia) {
  ag.dia = dia;
  ag.form = null;
  ag.painel = "dia";
  $("agenda").querySelectorAll("[data-ag-dia]").forEach((el) => {
    el.classList.toggle("ag-escolhido", el.dataset.agDia === dia);
  });
  await carregarDia();
  abrirDiaNoPopup();
}

function abrirFormAgenda(v) {
  fecharPopupDoDia();
  ag.form = v;
  ag.painel = "form";
  if (ag.visao === "mes") {
    // Do Mês, o compromisso se marca na Semana: a do dia dele. Em Tarefas e
    // compromissos ele fica, porque a lista também é dele.
    const dia = deIso(v.data || ag.dia);
    ag.dia = iso(dia);
    ag.semana = iso(segundaDe(dia));
    ag.visao = "semana";
    ag.zoom = "dias";
    return mostrarAgenda();
  }
  redesenharFormAgenda();
}

function abrirItem(chave) {
  const r = ag.itens[chave];
  if (!r) return;
  const x = r.item;
  if (x.genero === "compromisso") {
    const c = (ag.grade.compromissos || []).find((k) => k.id === x.id);
    if (c) verCompromisso(c);
    return;
  }
  if (x.genero === "documento") {
    bib.termo = x.titulo;
    marcarDestino("biblioteca");
    return mostrarBiblioteca();
  }
  abrirTarefaNaAgenda(x.id, r.dia, x.genero === "tarefa");
}

/* A tarefa abre na visao Tarefas e compromissos, no filtro em que ela esta,
   com a linha dela aberta. */
function abrirTarefaNaAgenda(id, dia, concluida) {
  fecharPopupDoDia();
  const hoje = iso(new Date());
  ag.tar.filtro = concluida ? "concluidas" : (dia && dia > hoje ? "planejadas" : "meu_dia");
  ag.tar.lista = "";
  ag.tar.aberta = id;
  ag.tar.aberto = null;
  ag.form = null;
  mostrarAgenda("tarefas");
}

/* ------------------------------------------------ o painel do dia */

function ligarPainelDoDia(p) {
  const d = ag.diaAberto;
  if (!d) return;
  const compromisso = (el, nome) => d.compromissos.find((x) => x.id === Number(el.dataset[nome]));

  p.querySelectorAll("[data-ag-marcar]").forEach((b) => { b.onclick = () => criarNaAgenda("compromisso"); });
  p.querySelectorAll("[data-ag-ir-tarefas]").forEach((b) => { b.onclick = () => adicionarTarefaNoDia(ag.dia); });
  p.querySelectorAll("[data-ag-ver]").forEach((el) => {
    el.onclick = () => { const c = compromisso(el, "agVer"); if (c) verCompromisso(c); };
  });
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
}

/* Adicionar tarefa pelo dia: o pop-up de cadastro, com o prazo no dia. */
function adicionarTarefaNoDia(dia) {
  fecharPopupDoDia();
  abrirFormAgenda({ tipo: "tarefa", prazo: dia, lista: ag.tar.lista || "" });
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
  // As listas com a cara das do sistema (a do Vínculo), e não a do navegador.
  p.querySelectorAll(".dialogo-caixa select").forEach(melhorarSelect);
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
  });
  const convite = p.querySelector("[data-ag-convite]");
  if (convite) convite.onclick = () => { v.convite = !v.convite; convite.classList.toggle("on", v.convite); };
  const apagar = p.querySelector("[data-ag-apagar]");
  if (apagar) apagar.onclick = async () => {
    // A pergunta de excluir toma o lugar do pop-up; desistir o traz de volta.
    const foi = await (v.tipo === "tarefa" ? apagarTarefa(v.id) : apagarCompromisso(v));
    if (!foi) abrirFormAgenda(v);
  };
  const titulo = p.querySelector('[data-c="titulo"]');
  if (titulo && !v.titulo) titulo.focus();
  if (v.tipo !== "tarefa") carregarLivres(p);
}

/* Os horarios em que cabe: o que era a tela de Agendamento. */
async function carregarLivres(p) {
  const alvo = p.querySelector("[data-ag-livres]");
  if (!alvo) return;
  const v = ag.form;
  if (!v.data) { alvo.innerHTML = '<span class="dialogo-dica">escolha a data</span>'; return; }
  alvo.innerHTML = '<span class="dialogo-dica">procurando…</span>';
  let d;
  try {
    d = await (await fetch("/api/agenda/livres?dia=" + v.data + "&duracao=" + (Number(v.duracao) || 60))).json();
  } catch (err) {
    alvo.innerHTML = "";
    return;
  }
  if (!d.horarios.length) {
    alvo.innerHTML = '<span class="dialogo-dica">nenhum horário livre neste dia com essa duração</span>';
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
          titulo: v.titulo.trim(), prazo: v.prazo || "", hora: v.prazo ? (v.hora || "") : "",
          lista: (v.lista || "").trim(), cadastro_id: v.cadastro_id || null, anotacao: v.anotacao || "",
          repetir: v.repetir || "", importante: v.importante || false, lembrar_em: v.lembrar_em || "",
        } }),
      });
      if (!r.ok) throw new Error(await erroDe(r));
      const t = await r.json();
      ag.form = null;
      ag.painel = "dia";
      ag.diaAberto = null;
      ag.tar.aberta = t.id;
      ag.tar.aberto = null;
      fecharFormNoPopup();
      await mostrarAgenda();
      if (!v.id) avisoCert("tarefa criada" + (t.prazo ? " para " + dataCurta(t.prazo) : ""));
      return;
    }

    const dados = {
      titulo: v.titulo.trim(), tipo: "compromisso", data: v.data, hora: v.hora || "09:00",
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
    fecharFormNoPopup();
    await mostrarAgenda();
    if (v.convite) enviarConvite(c.titulo, conviteDe(c, ""));
  } catch (err) {
    aviso.textContent = "não consegui salvar: " + (err.message || err);
  }
}

async function apagarCompromisso(c) {
  if (!(await confirmar({ titulo: "Excluir este compromisso?", contexto: "Agenda › " + c.titulo, texto: "Ele sai da agenda. " + LIXEIRA_TEXTO, confirmar: "Excluir", perigo: true }))) return false;
  const r = await fetch("/api/agenda/" + c.id, { method: "DELETE" });
  ag.form = null;
  ag.painel = "dia";
  ag.diaAberto = null;
  mostrarAgenda();
  avisarLixeira(r, () => mostrarAgenda());
  return true;
}

/* ------------------------------------------------- a ficha da tarefa */

function ligarFichaDaTarefa(p) {
  const t = ag.tar.itens.find((x) => x.id === ag.tar.aberta);
  if (!t) return;
  const editar = p.querySelector("[data-ag-editar-tarefa]");
  if (editar) editar.onclick = () => editarTarefa(t);

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
  /* O calendario com hora muda prazo e hora na mesma tacada: as duas
     mudancas viram uma gravacao so. Em duas, a segunda saia com o valor
     velho da primeira e desfazia o que a pessoa acabara de escolher. */
  let pendentes = null;
  let aGuardar = null;
  p.querySelectorAll("[data-ag-campo]").forEach((el) => {
    el.onchange = () => {
      const c = el.dataset.agCampo;
      pendentes = Object.assign(pendentes || {}, { [c]: c === "cadastro_id" ? (Number(el.value) || null) : el.value });
      clearTimeout(aGuardar);
      aGuardar = setTimeout(() => {
        const mudancas = pendentes;
        pendentes = null;
        salvarCamposDaTarefa(t, mudancas);
      }, 80);
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

/* O compromisso aberto na linha: as acoes dele, Editar e Excluir. */
function ligarFichaDoCompromisso(p) {
  const k = (ag.tar.compromissos || []).find((x) => x.id === ag.tar.aberto);
  if (!k) return;
  p.querySelectorAll("[data-ag-sala]").forEach((b) => { b.onclick = () => window.open(SALAS[b.dataset.agSala], "_blank"); });
  const copiar = p.querySelector("[data-ag-copiar]");
  if (copiar) copiar.onclick = () => copiarTexto(conviteDe(k, ""), "convite copiado");
  const link = p.querySelector("[data-ag-link]");
  if (link) link.onclick = () => pedirLinkDaSala(k);
  const editar = p.querySelector("[data-ag-editar-comp]");
  if (editar) editar.onclick = () => abrirFormAgenda(Object.assign({}, k));
  const apagar = p.querySelector("[data-ag-apagar-comp]");
  if (apagar) apagar.onclick = () => apagarCompromisso(k);
}

/* Editar a tarefa: o pop-up de cadastro, com o que ela tem hoje. */
function editarTarefa(t) {
  abrirFormAgenda({
    tipo: "tarefa", id: t.id, titulo: t.titulo, prazo: t.prazo || "", hora: t.hora || "",
    lista: t.lista || "", cadastro_id: t.cadastro_id || null, anotacao: t.anotacao || "",
    repetir: t.repetir || "", importante: t.importante, lembrar_em: t.lembrar_em || "",
  });
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
    titulo: t.titulo, importante: t.importante, prazo: t.prazo || "", hora: t.hora || "", lembrar_em: t.lembrar_em || "",
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
  if (!(await confirmar({ titulo: "Excluir esta tarefa?", contexto: "Agenda › " + (t.titulo || "tarefa"), texto: "Ela sai da lista, com as etapas. " + LIXEIRA_TEXTO, confirmar: "Excluir", perigo: true }))) return false;
  const r = await fetch("/api/tarefas/" + id, { method: "DELETE" });
  ag.tar.aberta = null;
  ag.form = null;
  ag.painel = ag.visao === "tarefas" ? "tarefa" : "dia";
  ag.diaAberto = null;
  recarregarAgenda();
  avisarLixeira(r, () => recarregarAgenda());
  return true;
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

/* Ligar documento: o mesmo pop-up de anexar do Assistente - Acervo ou Meu
   computador -, e nao uma lista solta dentro da ficha. O que vem de fora e
   copiado para o acervo antes, e o vinculo e pelo conteudo (SHA-1). */
async function escolherDocumentoParaTarefa(id) {
  const t = ag.tar.itens.find((x) => x.id === id) || {};
  abrirAnexar({
    titulo: "Ligar documento", contexto: "Agenda › " + (t.titulo || "tarefa"), verbo: "Ligar",
    aoAnexar: async (nomes) => {
      if (!nomes || !nomes.length) return;
      let docs = [];
      try {
        docs = (await (await fetch("/api/biblioteca")).json()).documentos || [];
      } catch (err) {
        docs = [];
      }
      for (const nome of nomes) {
        const d = docs.find((x) => x.nome === nome);
        await fetch("/api/tarefas/" + id + "/vincular", {
          method: "POST", headers: AG_JSON, body: JSON.stringify({ sha1: d ? d.sha1 : "", nome: nome }),
        });
      }
      carregarVinculosDaTarefa(id);
      avisoCert(plural(nomes.length, "documento") + (nomes.length === 1 ? " ligado" : " ligados") + " à tarefa", { tom: "ok" });
    },
  });
}

/* ---------------------------------------------- prazos dos documentos */

/* Os prazos que o assistente leu nos documentos, num pop-up de exibição:
   cada data com o botão de virar tarefa. */
async function abrirSugestoes() {
  let lidos;
  try {
    lidos = (await (await fetch("/api/tarefas/sugestoes")).json()).sugestoes;
  } catch (err) {
    avisoCert("não consegui ler os documentos");
    return;
  }
  ag.sugestoes = lidos;
  const escolha = dialogo({
    titulo: "Prazos lidos nos documentos",
    contexto: lidos.length ? plural(lidos.length, "data") + " que ainda não " + (lidos.length === 1 ? "virou" : "viraram") + " tarefa" : "nada a sugerir",
    classe: "dialogo-ver", larga: true, cancelar: "Fechar", confirmar: "Criar todas",
    html: '<div id="ag-sugestoes">' + (lidos.length
      ? "<p>Datas que o assistente já leu nos contratos abertos. Escolha as que quiser.</p>" +
        lidos.map((x, i) => '<div class="ag-ligado"><span class="duas-linhas"><b>' + esc(x.titulo) + "</b><small>" + dataLonga(x.prazo) +
          (x.cliente ? " · " + esc(x.cliente) : "") + '</small></span><button type="button" data-ag-aceitar="' + i + '">Criar</button></div>').join("")
      : "<p>Os documentos abertos não trazem data dentro dos próximos 90 dias, ou todas já viraram tarefa.</p>") + "</div>",
  });
  const caixa = document.getElementById("ag-sugestoes");
  if (caixa) ligarSugestoes(caixa);
  const r = await escolha;
  if (!r || !r.ok || !lidos.length) return;
  for (const x of lidos) await criarTarefaDaSugestao(x);
  avisoCert(plural(lidos.length, "tarefa") + (lidos.length === 1 ? " criada" : " criadas"), { tom: "ok" });
  mostrarAgenda();
}

async function criarTarefaDaSugestao(x) {
  const r = await fetch("/api/tarefas", {
    method: "POST", headers: AG_JSON,
    body: JSON.stringify({ dados: { titulo: x.titulo, prazo: x.prazo, lista: x.lista } }),
  });
  if (!r.ok) { avisoCert("não consegui criar: " + await erroDe(r)); return false; }
  ag.diaAberto = null;
  return true;
}

function ligarSugestoes(p) {
  p.querySelectorAll("[data-ag-aceitar]").forEach((b) => {
    b.onclick = async () => {
      if (!(await criarTarefaDaSugestao(ag.sugestoes[Number(b.dataset.agAceitar)]))) return;
      b.disabled = true;
      b.textContent = "criada";
      try { await carregarAgenda(); } catch (err) { return; }
      tituloDaAgenda();
    };
  });
}

