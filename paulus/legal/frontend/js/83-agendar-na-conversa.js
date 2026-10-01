/* ------------------------------------------- agendar pela conversa (T3) */
/*
   Pacote de telas de 01/10/2026: `Conversa - Agendar`. "Marque uma reunião
   com a Cooperativa Rio Fresco na quinta" deixa de ser o cartao pequeno de
   antes: a conversa mostra a SEMANA (os compromissos, as tarefas e as datas
   de documento de verdade, de /api/agenda) com o horario proposto tracejado,
   e o formulario inteiro da Agenda abre na coluna da direita (420 px) - o
   mesmo de js/07-agenda.js: compromisso ou tarefa, data, hora, os horarios em
   que cabe, duracao, aviso, com quem, onde, a sala do Meet, a anotacao e o
   convite por e-mail.

   Clicar numa hora vazia da semana muda o horario; mudar no formulario move
   o tracejado. Nada entra na agenda sem o "Marcar" (o /fazer de sempre, que
   anota na conversa e passa por Aprovacoes quando um agente pediu). O
   convite por e-mail continua passando por Aprovacoes antes de sair.
*/

const agc = {
  ativa: false,
  proposta: null,     // a proposta que abriu
  caixa: null,        // o cartao da semana, no chat
  semana: "",         // iso da segunda-feira vista
  grade: null,        // /api/agenda da semana
  vista: "semana",    // semana | mes
};

const AGC_PX_HORA = 56;
const AGC_DE = 7;
const AGC_ATE = 20;

/* O cartao da proposta. Ao vivo abre tudo; guardado, a conversa reaberta
   nao reabre formulario de compromisso que talvez ja tenha sido marcado. */
function cartaoDeAgendar() {
  return '<div class="agc-cartao" data-agc="1"><p class="explica">abrindo a agenda…</p></div>';
}

function ligarAgendarNaProposta(caixa, d) {
  agendarNaConversa(d, caixa);
}

async function agendarNaConversa(d, caixa) {
  const c = d.campos || {};
  const tarefa = d.tipo === "tarefa";
  // O formulario e o da Agenda: ag.form, com os mesmos campos.
  ag.dia = c.data || c.prazo || iso(new Date());
  ag.form = tarefa
    ? { tipo: "tarefa", titulo: c.titulo || "", prazo: c.prazo || "", hora: (c.lembrar_em || "").slice(11, 16),
        importante: Boolean(c.importante), lista: c.lista || "", cadastro_id: c.cadastro_id || null, anotacao: "" }
    : Object.assign(compromissoEmBranco("compromisso"), {
        titulo: c.titulo || "", data: c.data || "", hora: c.hora || proximaHoraCheia(), duracao: Number(c.duracao) || 60,
        avisar_min: Number(c.avisar_min) || 30, cadastro_id: c.cadastro_id || null, onde: c.onde || "online", anotacao: "",
      });
  Object.assign(agc, { ativa: true, proposta: d, caixa: caixa, vista: "semana",
    semana: iso(segundaDe(deIso(ag.form.data || ag.form.prazo || iso(new Date())))) });
  // As listas de clientes, listas e repeticoes que o formulario usa.
  try {
    const t = await (await fetch("/api/tarefas?filtro=meu_dia")).json();
    Object.assign(ag.tar, { clientes: t.clientes || [], listas: t.listas || [], repeticoes: t.repeticoes || [] });
  } catch (err) { /* o formulario abre sem as listas */ }
  if (typeof googleCarregado === "function" && gg.dados === null && !gg.tentou) googleCarregado();
  await carregarSemanaDaConversa();
  desenharSemanaNaConversa();
  abrirFormularioDeAgendar();
  $("pedido").placeholder = "Mude o dia, o horário ou quem vai…";
}

/* ------------------------------------------------ a semana, no chat */

async function carregarSemanaDaConversa() {
  const seg = deIso(agc.semana);
  const de = agc.vista === "mes" ? iso(new Date(seg.getFullYear(), seg.getMonth(), 1)) : agc.semana;
  const ate = agc.vista === "mes" ? iso(new Date(seg.getFullYear(), seg.getMonth() + 1, 0)) : iso(andarDias(seg, 6));
  try {
    agc.grade = await (await fetch("/api/agenda?de=" + de + "&ate=" + ate)).json();
  } catch (err) {
    agc.grade = { dias: {}, compromissos: [] };
  }
}

function minutosDe(hora) {
  const m = /^(\d{1,2}):(\d{2})/.exec(hora || "");
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

function horaDe(min) {
  return String(Math.floor(min / 60)).padStart(2, "0") + ":" + String(min % 60).padStart(2, "0");
}

function blocoNaSemana(x, dia) {
  const ini = minutosDe(x.hora);
  if (ini === null) return "";
  const comp = x.genero === "compromisso" ? ((agc.grade.compromissos || []).find((c) => c.id === x.id) || {}) : {};
  const dur = Number(comp.duracao) || (x.genero === "compromisso" ? 60 : 45);
  const topo = Math.max(0, (ini - AGC_DE * 60) / 60 * AGC_PX_HORA);
  const altura = Math.max(26, dur / 60 * AGC_PX_HORA - 4);
  const genero = generoDaMarca(x);
  const quando = x.genero === "compromisso" ? x.hora + "–" + horaDe(ini + dur) : (genero === "prazo" ? "vence " + x.hora : x.hora);
  const classe = "agc-bloco ag-" + genero;
  return '<div class="' + classe + '" style="top:' + topo + "px;height:" + altura + 'px" title="' + esc(x.titulo) + '">' +
    "<b>" + esc(x.titulo) + "</b><small>" + esc(quando) + "</small></div>";
}

function blocoDaProposta(dia) {
  const v = ag.form;
  if (!v || v.tipo === "tarefa" || v.data !== dia) return "";
  const ini = minutosDe(v.hora);
  if (ini === null) return "";
  const dur = Number(v.duracao) || 60;
  return '<div class="agc-bloco agc-proposta" style="top:' + ((ini - AGC_DE * 60) / 60 * AGC_PX_HORA) + "px;height:" +
    Math.max(26, dur / 60 * AGC_PX_HORA - 4) + 'px"><b>' + esc(v.titulo || "Compromisso") + "</b><small>" + esc(v.hora + "–" + horaDe(ini + dur)) + "</small></div>";
}

function htmlDaSemana() {
  const seg = deIso(agc.semana);
  const dias = [0, 1, 2, 3, 4, 5, 6].map((i) => andarDias(seg, i));
  const hoje = iso(new Date());
  const alvo = ag.form ? (ag.form.data || ag.form.prazo) : "";
  const g = agc.grade || { dias: {} };
  const cabeca = '<div class="agc-dias"><span></span>' + dias.map((d) => {
    const k = iso(d);
    return '<span class="agc-dia' + (k === alvo ? " alvo" : "") + (k === hoje ? " hoje" : "") + '"><small>' + DIAS_CURTOS[(d.getDay() + 6) % 7] +
      "</small><b>" + d.getDate() + "</b></span>";
  }).join("") + "</div>";
  let horas = "";
  for (let h = AGC_DE; h < AGC_ATE; h++) horas += '<div class="agc-hora"><span>' + String(h).padStart(2, "0") + ":00</span></div>";
  const colunas = dias.map((d) => {
    const k = iso(d);
    return '<div class="agc-col' + (k === alvo ? " alvo" : "") + '" data-agc-dia="' + k + '">' +
      (g.dias[k] || []).map((x) => blocoNaSemana(x, k)).join("") + blocoDaProposta(k) + "</div>";
  }).join("");
  return cabeca + '<div class="agc-rolagem" id="agc-rolagem"><div class="agc-grade" style="height:' + ((AGC_ATE - AGC_DE) * AGC_PX_HORA) + 'px">' +
    '<div class="agc-horas">' + horas + "</div>" + colunas + "</div></div>";
}

function htmlDoMes() {
  const seg = deIso(agc.semana);
  const primeiro = new Date(seg.getFullYear(), seg.getMonth(), 1);
  const inicio = segundaDe(primeiro);
  const alvo = ag.form ? (ag.form.data || ag.form.prazo) : "";
  const hoje = iso(new Date());
  const g = agc.grade || { dias: {} };
  let html = '<div class="agc-mes"><div class="agc-mes-cabeca">' + DIAS_CURTOS.map((d) => "<span>" + d + "</span>").join("") + "</div><div class=\"agc-mes-dias\">";
  for (let i = 0; i < 42; i++) {
    const d = andarDias(inicio, i);
    const k = iso(d);
    const n = (g.dias[k] || []).length;
    const fora = d.getMonth() !== primeiro.getMonth();
    html += '<button type="button" class="agc-mes-dia' + (fora ? " fora" : "") + (k === alvo ? " alvo" : "") + (k === hoje ? " hoje" : "") + '" data-agc-escolher="' + k + '">' +
      "<b>" + d.getDate() + "</b>" + (n ? "<small>" + plural(n, "item", "itens") + "</small>" : "") + "</button>";
  }
  return html + "</div></div>";
}

function tituloDaSemana() {
  const seg = deIso(agc.semana);
  if (agc.vista === "mes") return maiuscula(MESES_NOME[seg.getMonth()]) + " " + seg.getFullYear();
  const dom = andarDias(seg, 6);
  return seg.getDate() + (seg.getMonth() !== dom.getMonth() ? " " + MESES_NOME[seg.getMonth()].slice(0, 3) : "") +
    " – " + dom.getDate() + " " + MESES_NOME[dom.getMonth()].slice(0, 3) + " " + dom.getFullYear();
}

function desenharSemanaNaConversa() {
  const caixa = agc.caixa;
  if (!caixa || !caixa.isConnected) return;
  const g = agc.grade || { compromissos: [] };
  const n = (g.compromissos || []).length;
  caixa.innerHTML = '<div class="agc-cartao">' +
    '<div class="agc-topo">' + ic("calendar_month", 18) + "<b>Agenda</b><small>" +
    esc(agc.vista === "mes" ? plural(n, "compromisso") + " neste mês" : plural(n, "compromisso") + " esta semana") + "</small>" +
    '<span class="vazio-flex"></span><span class="visoes agc-vistas"><button data-agc-vista="mes"' + (agc.vista === "mes" ? ' class="ativa"' : "") + ">Mês</button>" +
    '<button data-agc-vista="semana"' + (agc.vista === "semana" ? ' class="ativa"' : "") + ">Semana</button></span>" +
    '<span class="divisa-v"></span><button class="botao-icone" data-agc-andar="-1" aria-label="Anterior">' + ic("chevron_left", 18) + "</button>" +
    '<b class="agc-periodo">' + esc(tituloDaSemana()) + "</b>" +
    '<button class="botao-icone" data-agc-andar="1" aria-label="Próxima">' + ic("chevron_right", 18) + "</button>" +
    '<button data-agc-hoje="1">Hoje</button></div>' +
    (agc.vista === "mes" ? htmlDoMes() : htmlDaSemana()) +
    '<div class="agc-pe">' + legendaDaAgenda(["compromisso", "prazo", "documento"], "") +
    '<span class="agc-legenda-proposta"><i></i>Proposta</span><span class="vazio-flex"></span><small>' +
    (agc.vista === "mes" ? "clique num dia para mudar a data" : "clique numa hora vazia para mudar o horário") + "</small></div></div>";
  ligarSemanaNaConversa();
}

function ligarSemanaNaConversa() {
  const caixa = agc.caixa;
  caixa.querySelectorAll("[data-agc-vista]").forEach((b) => {
    b.onclick = async () => { agc.vista = b.dataset.agcVista; await carregarSemanaDaConversa(); desenharSemanaNaConversa(); };
  });
  caixa.querySelectorAll("[data-agc-andar]").forEach((b) => {
    b.onclick = async () => {
      const seg = deIso(agc.semana);
      const passo = Number(b.dataset.agcAndar);
      agc.semana = iso(agc.vista === "mes" ? segundaDe(new Date(seg.getFullYear(), seg.getMonth() + passo, 1)) : andarDias(seg, 7 * passo));
      await carregarSemanaDaConversa();
      desenharSemanaNaConversa();
    };
  });
  const hoje = caixa.querySelector("[data-agc-hoje]");
  if (hoje) hoje.onclick = async () => { agc.semana = iso(segundaDe(new Date())); await carregarSemanaDaConversa(); desenharSemanaNaConversa(); };
  caixa.querySelectorAll("[data-agc-escolher]").forEach((b) => {
    b.onclick = () => mudarQuando(b.dataset.agcEscolher, null);
  });
  // Clicar numa hora vazia: o horario vai para la, de meia em meia hora.
  caixa.querySelectorAll("[data-agc-dia]").forEach((col) => {
    col.onclick = (e) => {
      if (e.target.closest(".agc-bloco:not(.agc-proposta)")) return;
      const r = col.getBoundingClientRect();
      const min = AGC_DE * 60 + Math.floor((e.clientY - r.top) / AGC_PX_HORA * 2) * 30;
      mudarQuando(col.dataset.agcDia, horaDe(Math.max(AGC_DE * 60, Math.min(AGC_ATE * 60 - 30, min))));
    };
  });
  // A semana abre no horario proposto.
  const rolagem = $("agc-rolagem");
  const ini = ag.form && minutosDe(ag.form.hora);
  if (rolagem && ini !== null) rolagem.scrollTop = Math.max(0, (ini - AGC_DE * 60) / 60 * AGC_PX_HORA - 140);
}

/* Muda a data (e a hora) no formulario e na semana juntos. */
function mudarQuando(dia, hora) {
  const v = ag.form;
  if (!v) return;
  if (v.tipo === "tarefa") v.prazo = dia; else v.data = dia;
  if (hora) v.hora = hora;
  const rolagem = $("agc-rolagem");
  const onde = rolagem ? rolagem.scrollTop : 0;
  redesenharFormularioDeAgendar();
  desenharSemanaNaConversa();
  if ($("agc-rolagem")) $("agc-rolagem").scrollTop = onde;
}

/* --------------------------------------------- o formulario, na coluna */

function htmlDoFormularioDeAgendar() {
  const v = ag.form;
  const f = partesDoFormAgenda(v);
  const dia = v.tipo === "tarefa" ? v.prazo : v.data;
  return '<div class="agc-form" data-fl-tipo="agendar">' +
    '<div class="agc-form-topo"><span class="visoes agc-tipo">' +
    '<button data-agc-tipo="compromisso"' + (v.tipo !== "tarefa" ? ' class="ativa"' : "") + ">" + ic("event", 16) + "Compromisso</button>" +
    '<button data-agc-tipo="tarefa"' + (v.tipo === "tarefa" ? ' class="ativa"' : "") + ">" + ic("task_alt", 16) + "Tarefa</button></span>" +
    '<span class="vazio-flex"></span><small>Agenda › ' + esc(dia ? maiuscula(diaCurto(dia)) : "sem data") + "</small></div>" +
    '<div class="agc-form-corpo dialogo-form" id="agc-form-corpo">' + f.corpo + "</div>" +
    '<div class="agc-form-pe"><span id="agc-resumo"></span><span class="vazio-flex"></span>' +
    '<span class="dialogo-aviso" data-ag-aviso="1"></span>' +
    '<button class="fantasma" data-agc-nao="1">Deixa pra lá</button>' +
    '<button class="primario" data-agc-marcar="1">' + ic("check", 16) + esc(f.botao) + "</button></div></div>";
}

function abrirFormularioDeAgendar() {
  abrirNoLado("formulario", {
    chave: "agendar",
    html: htmlDoFormularioDeAgendar(),
    ligar: ligarFormularioDeAgendar,
    aoFechar: () => {
      agc.ativa = false;
      ag.form = null;
      $("pedido").placeholder = "Pergunte outra coisa ou aponte outra pasta…";
    },
  });
}

function redesenharFormularioDeAgendar() {
  const lado = $("lado-ferramenta");
  if (!lado || papelDoLado() !== "formulario" || !agc.ativa) return;
  lado.innerHTML = htmlDoFormularioDeAgendar();
  ligarFormularioDeAgendar(lado);
}

function resumoDoAgendar() {
  const v = ag.form;
  if (!v) return "";
  if (v.tipo === "tarefa") return v.prazo ? maiuscula(diaCurto(v.prazo)) + (v.hora ? " · " + v.hora : "") : "sem prazo";
  const ini = minutosDe(v.hora);
  const onde = { online: "online", escritorio: "no escritório", telefone: "telefone" }[v.onde] || "";
  return [v.data ? maiuscula(diaCurto(v.data)) : "sem data", ini !== null ? v.hora + "–" + horaDe(ini + (Number(v.duracao) || 60)) : "", onde]
    .filter(Boolean).join(" · ");
}

function ligarFormularioDeAgendar(raiz) {
  ligarFormAgenda(raiz);
  const resumo = () => { const r = $("agc-resumo"); if (r) r.textContent = resumoDoAgendar(); };
  resumo();
  // Mudar no formulario move o tracejado na semana.
  raiz.addEventListener("input", () => { resumo(); desenharSemanaNaConversa(); });
  raiz.addEventListener("change", () => { resumo(); desenharSemanaNaConversa(); });
  raiz.addEventListener("click", (e) => { if (e.target.closest("[data-ag-livre], [data-ag-onde]")) setTimeout(() => { resumo(); desenharSemanaNaConversa(); }, 0); });
  raiz.querySelectorAll("[data-agc-tipo]").forEach((b) => {
    b.onclick = () => {
      const v = ag.form;
      if (b.dataset.agcTipo === (v.tipo === "tarefa" ? "tarefa" : "compromisso")) return;
      const dia = v.data || v.prazo || "";
      ag.form = b.dataset.agcTipo === "tarefa"
        ? { tipo: "tarefa", titulo: v.titulo, prazo: dia, hora: "", cadastro_id: v.cadastro_id, anotacao: v.anotacao || "" }
        : Object.assign(compromissoEmBranco("compromisso"), { titulo: v.titulo, data: dia, cadastro_id: v.cadastro_id, anotacao: v.anotacao || "" });
      redesenharFormularioDeAgendar();
      desenharSemanaNaConversa();
    };
  });
  raiz.querySelector("[data-agc-nao]").onclick = () => {
    const caixa = agc.caixa;
    voltarAoContexto();
    if (caixa && caixa.isConnected) caixa.innerHTML = '<p class="explica">Tudo bem — não anotei nada.</p>';
  };
  raiz.querySelector("[data-agc-marcar]").onclick = (e) => marcarPelaConversa(e.currentTarget);
}

/* Marcar: o /fazer de sempre (anota na conversa; com agente, passa por
   Aprovacoes). A sala do Meet nasce depois, pelo /api/agenda, e o convite
   abre o e-mail para revisar - e sai so pelas Aprovacoes. */
async function marcarPelaConversa(botao) {
  const v = ag.form;
  const d = agc.proposta || {};
  const aviso = document.querySelector("#lado-ferramenta [data-ag-aviso]");
  if (!(v.titulo || "").trim()) { if (aviso) aviso.textContent = "dê um título"; return; }
  const tarefa = v.tipo === "tarefa";
  if (!tarefa && !v.data) { if (aviso) aviso.textContent = "escolha a data"; return; }
  const campos = tarefa
    ? { titulo: v.titulo.trim(), prazo: v.prazo || "", hora: v.prazo ? (v.hora || "") : "", lista: (v.lista || "").trim(),
        cadastro_id: v.cadastro_id || null, anotacao: v.anotacao || "", repetir: v.repetir || "", importante: Boolean(v.importante),
        lembrar_em: v.prazo && v.lembrar_em ? v.prazo + " " + v.lembrar_em : "" }
    : { titulo: v.titulo.trim(), tipo: "compromisso", data: v.data, hora: v.hora || "09:00", duracao: Number(v.duracao) || 60,
        onde: v.onde || "", cadastro_id: v.cadastro_id || null, anotacao: v.anotacao || "", avisar_min: Number(v.avisar_min) || 0 };
  botao.disabled = true;
  let r;
  try {
    r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: tarefa ? "tarefa" : "agenda", campos: campos, pedido_id: d.pedido_id || "" }),
    });
  } catch (err) { r = null; }
  if (!r || !r.ok) {
    botao.disabled = false;
    if (aviso) aviso.textContent = "não consegui marcar: " + (r ? await erroDe(r) : "sem resposta");
    return;
  }
  const feito = await r.json();
  const sala = !tarefa && querSalaDoMeet(v);
  const convite = !tarefa && v.convite;
  let comp = feito.registro || {};
  if (sala && feito.id) {
    if (aviso) aviso.textContent = "criando a sala do Meet…";
    try {
      const m = await fetch("/api/agenda", { method: "POST", headers: AG_JSON, body: JSON.stringify({ id: feito.id, dados: campos, meet: true }) });
      if (m.ok) comp = await m.json();
    } catch (err) { /* o compromisso ja esta marcado; a sala diz o que houve */ }
    avisarSalaDoMeet(comp, true, convite);
  }
  const caixa = agc.caixa;
  const semana = agc.semana;
  voltarAoContexto();
  notaDeFeitoNaConversa((feito.resumo || "Anotei") + (comp.meet ? ", com a sala do Meet" : "") + ".");
  if (caixa && caixa.isConnected) {
    // A semana fica, ja com o compromisso marcado (sem o tracejado).
    agc.caixa = caixa;
    agc.semana = semana;
    await carregarSemanaDaConversa();
    desenharSemanaNaConversa();
    caixa.querySelectorAll("[data-agc-dia]").forEach((col) => { col.onclick = null; });
    agc.caixa = null;
  }
  if (convite && comp.id) enviarConvite(comp.titulo || campos.titulo, conviteDe(comp, comp.meet || ""));
}
