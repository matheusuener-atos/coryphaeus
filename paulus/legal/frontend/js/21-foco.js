/* ------------------------------------------------------ foco e bem-estar */
/*
   Foco e bem-estar (docs/ui/03-telas-desktop.md, A12): Hoje e Semana, com o
   painel fixo. Tudo calculado so com uso local: o ciclo, os lembretes e a
   medicao de atividade sao os de sempre; o ritmo por hora sai das tarefas
   concluidas de hoje, e o parecer da semana e regra sobre os totais, nao
   opiniao de modelo. O que ainda nao tem motor - segurar e-mail, WhatsApp e
   Aprovacoes durante o foco, o historico por dia de cada lembrete - diz isso.
*/

const be = {
  visao: "hoje", dados: null, rel: null, tarefas: [], semanaAntes: null,
  relogio: null, ajustando: false, form: null, sugestaoDepois: false, tarefa: "",
};

const BE_JSON = { "Content-Type": "application/json" };
const BE_HORAS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18];

async function mostrarFoco(visao) {
  if (visao) be.visao = visao;
  pararRelogioDoFoco();
  abrirTela("Foco e bem-estar", { cheia: true });
  marcarDestino("foco");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  atualizarPostura();
  try {
    const pega = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    const [d, rel, t] = await Promise.all([
      fetch("/api/bemestar").then((r) => r.json()), pega("/api/relatorios"), pega("/api/tarefas?filtro=meu_dia"),
    ]);
    be.dados = d;
    be.rel = rel;
    be.tarefas = (t && t.tarefas) || [];
    if (be.visao === "semana") {
      const antes = deIso(d.semana.de);
      antes.setDate(antes.getDate() - 1);
      be.semanaAntes = await pega("/api/bemestar/semana?ate=" + iso(antes));
    }
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharFoco();
}

function desenharFoco() {
  cabecalhoFoco();
  const miolo = be.visao === "semana" ? corpoDaSemana() + painelDaSemana() : corpoDeHoje() + painelDeHoje();
  $("centro").innerHTML = '<div class="acervo be-tela" id="be-tela">' + miolo + "</div>";
  ligarFoco();
  atualizarPostura();
}

/* ------------------------------------------------------ o cabecalho */

function cabecalhoFoco() {
  const d = be.dados;
  const h = d.hoje;
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  titulo.textContent = "Foco e bem-estar";
  if (be.visao === "semana") {
    const s = d.semana;
    meta.textContent = "Semana de " + dataCurta(s.de) + " a " + dataCurta(s.ate) + " · " + horasEmTexto(minutosDaSemana(s)) + " de atividade";
  } else if (h.medindo) {
    const classe = "fin-meta-ponto" + (h.sem_pausa_min >= 90 ? " acc" : "");
    meta.innerHTML = "Ativo há " + esc(h.ativo_texto === "ainda nada hoje" ? "menos de um minuto" : h.ativo_texto) +
      '<span class="' + classe + '"><i></i>' + (h.sem_pausa_min ? "sem pausa há " + esc(horasEmTexto(h.sem_pausa_min)) : "medindo agora") + "</span>";
  } else {
    meta.textContent = "acompanhamento desligado · o ciclo de foco e os lembretes funcionam do mesmo jeito";
  }
  const botao = (v, r) => {
    const classe = v === be.visao ? "ativa" : "";
    return '<button class="' + classe + '" data-be-visao="' + v + '">' + r + "</button>";
  };
  $("acoes-tela").innerHTML = '<div class="visoes">' + botao("hoje", "Hoje") + botao("semana", "Semana") + "</div>" +
    '<button class="com-icone" data-be-ajustar="1">' + ic("tune", 16) + (be.ajustando ? "Fechar os ajustes" : "Ajustar lembretes") + "</button>" +
    '<button class="com-icone' + (h.medindo ? "" : " primario") + '" data-be-medir="1">' + ic(h.medindo ? "visibility_off" : "visibility", 16) +
    (h.medindo ? "Desligar acompanhamento" : "Ligar acompanhamento") + "</button>";
  $("nav-tela").innerHTML = "";
}

/* --------------------------------------------------------- miudezas */

function horasEmTexto(minutos) {
  const m = Math.round(minutos || 0);
  if (!m) return "0 min";
  if (m < 60) return m + " min";
  return Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0") + " min";
}

function horasCurtas(minutos) {
  if (!minutos) return "—";
  return String(Math.round(minutos / 6) / 10).replace(".", ",") + " h";
}

function minutosDaSemana(s) {
  return (s.dias || []).reduce((soma, x) => soma + (x.minutos_ativos || 0), 0);
}

function feitasPorHora() {
  const contagem = BE_HORAS.map(() => 0);
  const feitas = (((be.rel || {}).dia || {}).tarefas || {}).feitas || [];
  feitas.forEach((t) => {
    const hora = Number(String(t.hora || "").slice(0, 2));
    const i = BE_HORAS.indexOf(hora);
    if (i >= 0) contagem[i] += 1;
  });
  return contagem;
}

function faseDoCiclo(c) {
  if (c.estado === "foco") return "foco · ciclo " + c.numero;
  if (c.estado === "pausa") return "pausa · depois do ciclo " + c.numero;
  return "parado";
}

function progressoDoCiclo(c) {
  if (c.estado === "parado" || !c.duracao) return 0;
  return Math.max(0, Math.min(100, Math.round((1 - c.restante / c.duracao) * 100)));
}

/* -------------------------------------------------------------- hoje */

function corpoDeHoje() {
  const d = be.dados;
  const c = d.ciclo;
  const lembretes = d.lembretes || [];
  const cumpridos = lembretes.filter((l) => l.cumprido).length;
  const classeAnel = "be-anel" + (c.estado === "pausa" ? " pausa" : (c.estado === "parado" ? " parado" : ""));
  let botoes;
  if (c.estado === "parado") {
    botoes = '<button class="primario" data-be-comecar="1">' + ic("play_arrow", 16) + "Começar</button>";
  } else if (c.estado === "foco") {
    botoes = '<button class="primario" data-be-pausa="1">' + ic("skip_next", 16) + "Ir para a pausa</button>" +
      '<button data-be-reiniciar="1">' + ic("restart_alt", 16) + "Reiniciar</button>" +
      '<button data-be-parar="1">' + ic("stop", 16) + "Parar</button>";
  } else {
    botoes = '<button class="primario" data-be-comecar="1">' + ic("play_arrow", 16) + "Novo ciclo</button>" +
      '<button data-be-parar="1">' + ic("stop", 16) + "Parar</button>";
  }
  const tarefaAtual = be.tarefa || c.tarefa || "";
  const opcoes = '<option value="">nenhuma — só o tempo</option>' + be.tarefas.map((t) =>
    '<option value="' + esc(t.titulo) + '"' + (t.titulo === tarefaAtual ? " selected" : "") + ">" + esc(t.titulo) + "</option>").join("") +
    (tarefaAtual && !be.tarefas.some((t) => t.titulo === tarefaAtual) ? '<option value="' + esc(tarefaAtual) + '" selected>' + esc(tarefaAtual) + "</option>" : "");

  const ciclo = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Ciclo de foco</span><small>' +
    esc(c.tarefa ? "tarefa deste ciclo: " + c.tarefa : "sem tarefa marcada") + "</small></div>" +
    '<div class="be-ciclo">' +
    '<div class="' + classeAnel + '" id="be-anel" style="--be-p:' + progressoDoCiclo(c) + '%"><div><span class="be-tempo" id="be-relogio">' +
    esc(c.estado === "parado" ? String(c.foco_min).padStart(2, "0") + ":00" : c.restante_texto) + '</span><span class="be-fase" id="be-fase">' + esc(faseDoCiclo(c)) + "</span></div></div>" +
    '<div class="be-botoes">' + botoes + "</div>" +
    '<div class="be-ajustes"><div><small>Foco</small><select data-be-foco="1"' + (c.estado === "parado" ? "" : " disabled") + ">" +
    [15, 25, 45, 50, 90].map((m) => '<option value="' + m + '"' + (c.foco_min === m ? " selected" : "") + ">" + m + " min</option>").join("") + "</select></div>" +
    '<div><small>Pausa</small><select data-be-pausa-min="1"' + (c.estado === "parado" ? "" : " disabled") + ">" +
    [5, 10, 15].map((m) => '<option value="' + m + '"' + (c.pausa_min === m ? " selected" : "") + ">" + m + " min</option>").join("") + "</select></div></div>" +
    '<div class="be-tarefa ag-campo"><label>Tarefa deste ciclo</label><select data-be-tarefa="1"' + (c.estado === "parado" ? "" : " disabled") + ">" + opcoes + "</select></div>" +
    '<div class="cfg-liga presa"><span class="duas-linhas"><b>Silenciar avisos durante o foco</b><small>segurar e-mail, WhatsApp e Aprovações até a pausa ainda não existe</small></span><i></i></div>' +
    "</div></div>";

  const linhas = lembretes.map((l) => {
    const atrasado = l.ligado && !l.cumprido && l.atrasado_min > 0;
    const classe = "be-lembrete" + (atrasado ? " atrasado" : "") + (l.ligado ? "" : " desligado");
    const classeSub = atrasado ? "acc" : "";
    let sub;
    if (!l.ligado) sub = "desligado · " + l.meta_texto;
    else if (atrasado) sub = l.meta_texto + (l.meta_dia ? "" : " feito") + " · atrasado " + horasEmTexto(l.atrasado_min);
    else sub = "a cada " + horasEmTexto(l.cada_min) + (l.meta_dia ? " · " + l.meta_texto : "") + (l.proximo ? " · próximo às " + l.proximo : "");
    const agua = /água|agua/i.test(l.titulo);
    return '<div class="' + classe + '">' + (l.cumprido ? ic("check_circle", 18) : '<span class="be-marca"></span>') +
      '<span class="duas-linhas"><b>' + esc(l.titulo) + '</b><small class="' + classeSub + '">' + esc(sub) + "</small></span>" +
      (l.ligado && !l.cumprido ? '<button' + (atrasado ? ' class="primario"' : "") + ' data-be-feito="' + l.id + '">' + (agua ? "Bebi" : "Feito") + "</button>" : "") + "</div>";
  }).join("");
  const lista = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Lembretes de hoje</span><small>' + cumpridos + " de " + lembretes.length + "</small></div>" +
    '<div class="be-lembretes">' + (linhas || '<p class="rel-vazio">Nenhum lembrete. Crie um em Ajustar lembretes.</p>') + "</div>" +
    '<div class="be-rodape"><span>Lembretes ficam nesta máquina · nada é compartilhado</span><button class="em-ligacao forte" data-be-ajustar="1">Ajustar lembretes →</button></div></div>';

  return '<div class="acervo-principal"><div class="be-grade">' + ciclo + lista + "</div></div>";
}

function painelDeHoje() {
  if (be.ajustando) return painelDosAjustes();
  const d = be.dados;
  const h = d.hoje;
  const c = d.ciclo;
  const porHora = feitasPorHora();
  const teto = Math.max(1, ...porHora);
  const agora = new Date().getHours();
  const dia = ((be.rel || {}).dia) || {};
  const t = dia.tarefas || { feitas: [], abertas: [], planejado: 0 };
  const total = porHora.reduce((s, x) => s + x, 0);

  const barras = BE_HORAS.map((hora, i) => {
    const classe = porHora[i] ? (hora === agora ? "agora" : "") : "vazia";
    return '<span class="' + classe + '" title="' + hora + 'h · ' + esc(plural(porHora[i], "tarefa concluída", "tarefas concluídas")) + '" style="height:' +
      (porHora[i] ? Math.max(8, Math.round(porHora[i] * 100 / teto)) : 2) + '%"></span>';
  }).join("");
  let leitura;
  if (total) {
    const melhor = porHora.indexOf(Math.max(...porHora));
    leitura = "Você concluiu mais por volta das " + BE_HORAS[melhor] + "h.";
  } else {
    leitura = "Nenhuma tarefa concluída hoje ainda — as barras sobem quando você fechar uma na Agenda.";
  }
  if (h.medindo && h.sem_pausa_min >= 60) leitura += " Está sem pausa há " + horasEmTexto(h.sem_pausa_min) + (c.estado === "foco" ? " — a próxima cai no fim deste ciclo." : ".");
  else if (c.estado === "foco") leitura += " A próxima pausa cai em " + horasEmTexto(Math.ceil(c.restante / 60)) + ", no fim deste ciclo.";

  const sugestao = sugestaoParaAgora();
  const toggles = (d.lembretes || []).map((l) => ligaCfg("lembrete:" + l.id, "Lembrar de " + l.titulo.charAt(0).toLowerCase() + l.titulo.slice(1),
    "a cada " + horasEmTexto(l.cada_min) + (l.meta_dia ? " · " + l.meta_dia + " por dia" : ""), Boolean(l.ligado))).join("");

  return '<aside class="acervo-painel be-painel"><div class="rolagem">' +
    '<div class="fin-bloco-cabeca fin-painel-topo">' + (h.medindo ? coroa(18) : "") + "<span>Seu ritmo hoje</span><small>" +
    esc(h.medindo ? "ativo há " + (h.ativo_texto === "ainda nada hoje" ? "pouco" : h.ativo_texto) : "sem medição") + "</small></div>" +
    '<div class="be-ritmo"><div class="be-horas">' + barras + "</div>" +
    '<div class="be-horas-rotulos">' + BE_HORAS.map((x) => "<span>" + x + "h</span>").join("") + "</div>" +
    "<p>" + esc(leitura) + '</p><span class="cfg-explica">barras: tarefas concluídas por hora, hoje · o tempo ativo é somado por dia</span></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Hoje</span></div><div class="cfg-chaves">' +
    chaveCfg("Tempo ativo", h.medindo || h.minutos_ativos ? h.ativo_texto : "sem medição", h.medindo || h.minutos_ativos ? "" : "mute") +
    chaveCfg("Ciclos de foco", String(h.ciclos || 0)) +
    chaveCfg("Pausas feitas", String(h.pausas || 0)) +
    chaveCfg("Tarefas concluídas", t.feitas.length + (t.planejado ? " de " + t.planejado : "")) +
    chaveCfg("Água", plural(h.copos_agua || 0, "copo")) +
    chaveCfg("Maior sequência sem pausa", h.seguida_texto) + "</div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Sugestão para agora</span></div>' +
    '<div class="be-sugestao">' + ic("self_improvement", 18) + "<span><span>" + esc(sugestao.texto) + "</span>" +
    (sugestao.acoes.length ? '<span class="fin-pede-acoes">' + sugestao.acoes.map((a, j) => {
      const classe = a.primario ? "primario" : "";
      return '<button class="' + classe + '" data-be-sugestao="' + j + '">' + esc(a.rotulo) + "</button>";
    }).join("") + "</span>" : "") + "</span></div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Lembretes</span><span class="contagem">ligar e desligar</span></div>' +
    (toggles || "<p>Nenhum lembrete ainda.</p>") +
    ligaCfg("", "Modo foco silencia o WhatsApp", "em breve", false, true) +
    ligaCfg("", "Sugestões do assistente sobre ritmo", "com base só no uso local · em breve", false, true) + "</div>" +
    '<div class="painel-chaves">' + chaveCfg("Como eu meço", "tempo desde o último toque", "") + chaveCfg("Dados", "ficam nesta máquina") + "</div>" +
    "</div></aside>";
}

/* A sugestao sai do que foi medido ou do que esta marcado: sem motivo, ela
   diz que nao ha motivo. */
function sugestaoParaAgora() {
  const d = be.dados;
  const c = d.ciclo;
  if (d.alerta && !be.sugestaoDepois) {
    return { texto: d.alerta.titulo + ". " + d.alerta.detalhe, acoes: [
      { rotulo: "Ir para a pausa", primario: true, fazer: () => irParaPausaDoFoco() },
      { rotulo: "Depois", fazer: () => { be.sugestaoDepois = true; desenharFoco(); } },
    ] };
  }
  if (c.estado === "foco" && c.tarefa) {
    return { texto: "Feche “" + c.tarefa + "” neste ciclo: faltam " + horasEmTexto(Math.ceil(c.restante / 60)) + ". Depois, pausa de " + c.pausa_min + " min longe da tela.", acoes: [
      { rotulo: "Ver na Agenda", fazer: () => { marcarDestino("calendario"); mostrarAgenda("tarefas"); } },
    ] };
  }
  if (c.estado === "pausa") {
    return { texto: "Pausa: levante, beba água e olhe para longe. O próximo ciclo começa quando você voltar.", acoes: [] };
  }
  if (be.tarefas.length && c.estado === "parado") {
    const t = be.tarefas[0];
    return { texto: "Comece por “" + t.titulo + "”, que está no seu Meu dia. Um ciclo de " + c.foco_min + " min costuma bastar para destravar.", acoes: [
      { rotulo: "Usar neste ciclo", primario: true, fazer: () => { be.tarefa = t.titulo; comecarCicloDoFoco(); } },
      { rotulo: "Depois", fazer: () => { be.sugestaoDepois = true; desenharFoco(); } },
    ] };
  }
  const atrasado = (d.lembretes || []).find((l) => l.ligado && !l.cumprido && l.atrasado_min > 0);
  if (atrasado) {
    return { texto: atrasado.titulo + " está atrasado há " + horasEmTexto(atrasado.atrasado_min) + ". Dois minutos resolvem.", acoes: [
      { rotulo: "Feito", primario: true, fazer: () => marcarLembreteFeito(atrasado.id) },
    ] };
  }
  return { texto: d.hoje.medindo ? "Nada medido que peça ação agora. Comece um ciclo quando quiser." : "Ligue o acompanhamento para eu sugerir pausas pelo que foi medido — sem isso, prefiro não opinar.", acoes: [] };
}

/* Ajustar lembretes: a lista com editar e apagar, e o formulario de um. */
function painelDosAjustes() {
  const d = be.dados;
  const v = be.form;
  let miolo;
  if (v) {
    miolo = '<div class="ag-form fin-form">' +
      '<div class="ag-campo"><label>O que lembrar</label><input type="text" data-be-campo="titulo" value="' + esc(v.titulo || "") + '" placeholder="Beber água"></div>' +
      '<div class="ag-duas"><div class="ag-campo"><label>A cada</label><select data-be-campo="cada_min">' +
      [15, 20, 25, 30, 45, 60, 90, 120, 180, 240].map((m) => '<option value="' + m + '"' + (Number(v.cada_min) === m ? " selected" : "") + ">" + horasEmTexto(m) + "</option>").join("") + "</select></div>" +
      '<div class="ag-campo"><label>Meta por dia</label><input type="text" data-be-campo="meta_dia" value="' + esc(v.meta_dia || "") + '" placeholder="0 = sem meta"></div></div>' +
      '<div class="ag-form-rodape">' + (v.id ? '<button class="perigo" data-be-tirar="' + v.id + '">Apagar</button>' : "") +
      '<button data-be-cancelar="1">Cancelar</button><button class="primario" data-be-guardar="1">Guardar</button></div></div>';
  } else {
    miolo = '<div class="be-editor">' + (d.lembretes || []).map((l) =>
      '<div class="be-editor-linha"><span class="duas-linhas"><b>' + esc(l.titulo) + "</b><small>a cada " + esc(horasEmTexto(l.cada_min)) +
      (l.meta_dia ? " · meta " + l.meta_dia + " por dia" : " · sem meta") + (l.ligado ? "" : " · desligado") + "</small></span>" +
      '<button data-be-editar="' + l.id + '">Editar</button><button class="botao-icone" data-be-tirar="' + l.id + '" title="Apagar">' + ic("close", 16) + "</button></div>").join("") +
      "</div>" +
      '<div class="fin-botoes fin-painel-botoes"><button class="primario" data-be-novo="1">' + ic("add", 16) + "Novo lembrete</button></div>";
  }
  return '<aside class="acervo-painel be-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + (v ? (v.id ? "Editar lembrete" : "Novo lembrete") : "Ajustar lembretes") + '</h3><span class="meta">tocam só nesta máquina</span></span>' +
    '<button class="botao-icone" data-be-ajustar="1" title="Fechar">' + ic("close", 18) + "</button></div>" + miolo +
    '<div class="painel-chaves"><div class="chave-valor"><span>Água</span><b>um lembrete com “água” no nome conta copos</b></div></div>' +
    "</div></aside>";
}

/* ------------------------------------------------------------ semana */

function corpoDaSemana() {
  const s = be.dados.semana;
  const dias = s.dias || [];
  const hoje = iso(new Date());
  const teto = Math.max(1, ...dias.map((x) => x.minutos_ativos || 0));
  const comDado = dias.filter((x) => x.minutos_ativos || x.ciclos || x.pausas);
  const total = minutosDaSemana(s);
  const media = comDado.length ? total / comDado.length : 0;
  const melhor = comDado.length ? comDado.reduce((a, b) => (b.minutos_ativos > a.minutos_ativos ? b : a)) : null;

  const barras = dias.map((x) => {
    const classe = "be-dia" + (x.dia === hoje ? " hoje" : "") + (x.minutos_ativos ? "" : " vazio");
    return '<div class="' + classe + '"><small>' + esc(horasCurtas(x.minutos_ativos)) + '</small><i style="height:' +
      (x.minutos_ativos ? Math.max(4, Math.round(x.minutos_ativos * 100 / teto)) : 2) + '%"></i></div>';
  }).join("");
  const rotulos = dias.map((x) => "<span>" + esc(maiuscula(x.rotulo)) + "<small>" + esc(x.pausas ? plural(x.pausas, "pausa") : "—") + "</small></span>").join("");

  const foco = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Foco na semana</span><small>' +
    esc(dataCurta(s.de) + " a " + dataCurta(s.ate) + " · " + horasEmTexto(total)) + "</small></div>" +
    '<div class="fin-fluxo"><div class="be-semana-grade">' + barras + "</div>" +
    '<div class="be-semana-rotulos">' + rotulos + "</div>" +
    '<div class="be-semana-somas"><div><small>Média por dia medido</small><b>' + esc(comDado.length ? horasEmTexto(media) : "—") + "</b></div>" +
    "<div><small>Dia mais ativo</small><b>" + esc(melhor ? maiuscula(melhor.rotulo) + " · " + horasEmTexto(melhor.minutos_ativos) : "—") + "</b></div>" +
    "<div><small>Pausas feitas</small><b>" + esc(s.pausas + " em " + plural(s.ciclos, "ciclo")) + "</b></div></div>" +
    (s.tem_dado ? "" : '<p class="cfg-explica">Nenhum dia com medição nesta semana. Ligue o acompanhamento e a semana aparece aqui — sem isso, qualquer gráfico seria invenção.</p>') +
    "</div></div>";

  const celulas = (valor, meta, dia) => {
    let classe;
    if (dia > hoje) classe = "futuro";
    else if (valor >= meta) classe = "cheio";
    else if (valor > 0) classe = "meio";
    else classe = "";
    return '<i class="' + classe + '" title="' + esc(maiuscula(dia === hoje ? "hoje" : dataCurta(dia)) + " · " + valor) + '"></i>';
  };
  const habitos = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Hábitos</span><small>semana</small></div><div class="be-habitos">' +
    '<div class="be-habito"><span>Beber água</span>' + dias.map((x) => celulas(x.copos_agua || 0, 8, x.dia)).join("") + "<small>meta 8 copos</small></div>" +
    '<div class="be-habito"><span>Pausas entre ciclos</span>' + dias.map((x) => celulas(x.pausas || 0, 4, x.dia)).join("") + "<small>meta 4</small></div>" +
    '<div class="be-habito"><span>Ciclos de foco</span>' + dias.map((x) => celulas(x.ciclos || 0, 4, x.dia)).join("") + "<small>meta 4</small></div>" +
    '<div class="be-habito adiante"><span>Levantar, alongar, almoço sem tela</span>' + dias.map(() => '<i class="futuro"></i>').join("") + "<small>histórico por dia em breve</small></div>" +
    "</div></div>";

  return '<div class="acervo-principal"><div class="be-grade semana">' + foco + habitos + "</div></div>";
}

/* O parecer e regra sobre os totais da semana: quem foi o dia mais ativo,
   onde a agua ficou abaixo, quantas pausas. Nada e opiniao de modelo. */
function parecerDaSemana() {
  const s = be.dados.semana;
  const dias = s.dias || [];
  const comDado = dias.filter((x) => x.minutos_ativos || x.ciclos || x.pausas);
  if (!comDado.length) return { lead: "Nenhum dia com medição nesta semana.", resto: "Ligue o acompanhamento e o parecer aparece aqui. Sem medição, qualquer frase seria invenção — e eu prefiro não opinar.", sugestoes: [] };
  const melhor = comDado.reduce((a, b) => (b.minutos_ativos > a.minutos_ativos ? b : a));
  const pior = comDado.reduce((a, b) => (b.minutos_ativos < a.minutos_ativos ? b : a));
  const aguaAbaixo = comDado.filter((x) => (x.copos_agua || 0) < 8).length;
  const pausasMedia = comDado.reduce((t, x) => t + (x.pausas || 0), 0) / comDado.length;
  let lead = maiuscula(melhor.rotulo) + " foi seu dia mais ativo: " + horasEmTexto(melhor.minutos_ativos) + " com " + plural(melhor.pausas, "pausa") + ".";
  if (pior !== melhor) lead += " " + maiuscula(pior.rotulo) + " ficou em " + horasEmTexto(pior.minutos_ativos) + ".";
  const resto = "Água abaixo da meta em " + aguaAbaixo + " de " + plural(comDado.length, "dia medido", "dias medidos") + ". Pausas: " + s.pausas + " no total, " +
    String(Math.round(pausasMedia * 10) / 10).replace(".", ",") + " por dia" + (s.maior_seguida > 90 ? ". Maior sequência sem parar: " + s.maior_seguida_texto + "." : ".");
  const sugestoes = [];
  const agua = (be.dados.lembretes || []).find((l) => /água|agua/i.test(l.titulo));
  if (aguaAbaixo && agua && agua.cada_min > 45) sugestoes.push({ texto: "Lembrete de água a cada 45 min em vez de " + horasEmTexto(agua.cada_min) + ".", tarefa: "Ajustar o lembrete de água para 45 min" });
  else if (aguaAbaixo) sugestoes.push({ texto: "Marcar “Bebi” quando beber: a meta de 8 copos só sobe com o registro.", tarefa: "Registrar a água no PAULUS" });
  if (pausasMedia < 3) sugestoes.push({ texto: "Fechar cada ciclo com a pausa — hoje a média é " + String(Math.round(pausasMedia * 10) / 10).replace(".", ",") + " por dia.", tarefa: "Fazer as pausas entre os ciclos de foco" });
  if (s.maior_seguida > 120) sugestoes.push({ texto: "Houve mais de 2 h sem parar: o alerta de pausa entra aos 90 min, aceite quando ele aparecer.", tarefa: "Aceitar o alerta de pausa aos 90 min" });
  if (comDado.length < 5) sugestoes.push({ texto: "Ligar o acompanhamento todos os dias úteis, para o parecer da semana valer.", tarefa: "Ligar o acompanhamento de foco ao começar o dia" });
  return { lead: lead, resto: resto, sugestoes: sugestoes };
}

function painelDaSemana() {
  const s = be.dados.semana;
  const p = parecerDaSemana();
  const antes = be.semanaAntes;
  const totalAntes = antes ? minutosDaSemana(antes) : null;
  const variacao = totalAntes === null ? null : minutosDaSemana(s) - totalAntes;
  return '<aside class="acervo-painel be-painel"><div class="rolagem">' +
    '<div class="fin-bloco-cabeca fin-painel-topo"><span>Parecer da semana</span><small>só com dados locais</small></div>' +
    '<div class="fin-parecer solto"><p class="fin-lead">' + esc(p.lead) + "</p><p>" + esc(p.resto) + "</p></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Sugestões</span><span class="contagem">' + (p.sugestoes.length ? "saem de regra, não de opinião" : "") + "</span></div>" +
    (p.sugestoes.length
      ? '<div class="fin-sugestoes">' + p.sugestoes.map((x) => '<div class="fin-sugestao"><i></i><span>' + esc(x.texto) + "</span></div>").join("") + "</div>"
      : "<p>Nada a sugerir com o que foi medido.</p>") +
    '<div class="fin-sug-rodape"><button class="em-ligacao" data-be-inutil="1">Não foi útil</button>' +
    '<button class="primario" data-be-agenda="1"' + (p.sugestoes.length ? "" : " disabled") + ">" + ic("calendar_month", 16) + "Aplicar na Agenda</button></div></div>" +
    '<div class="painel-chaves">' +
    chaveCfg("Semana anterior", totalAntes === null ? "—" : horasEmTexto(totalAntes)) +
    chaveCfg("Variação", variacao === null ? "—" : (variacao >= 0 ? "+ " : "− ") + horasEmTexto(Math.abs(variacao)), variacao === null ? "mute" : "") +
    chaveCfg("Dados", "ficam nesta máquina") + "</div></div></aside>";
}

/* ------------------------------------------------------------ as acoes */

function ligarFoco() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });

  clique("[data-be-visao]", (b) => { be.visao = b.dataset.beVisao; be.ajustando = false; be.form = null; mostrarFoco(); });
  clique("[data-be-ajustar]", () => { be.ajustando = !be.ajustando; be.form = null; if (be.visao !== "hoje") { be.visao = "hoje"; mostrarFoco(); return; } desenharFoco(); });
  clique("[data-be-medir]", async () => {
    const r = await fetch("/api/bemestar/medir", { method: "POST", headers: BE_JSON, body: JSON.stringify({ ligar: !be.dados.hoje.medindo }) });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    avisoCert(be.dados.hoje.medindo ? "acompanhamento desligado — nada mais é gravado" : "acompanhamento ligado — só o tempo desde o último toque, nunca o que foi digitado");
    mostrarFoco();
  });
  cada("[data-be-tarefa]", (el) => { el.onchange = () => { be.tarefa = el.value; }; });
  clique("[data-be-comecar]", () => comecarCicloDoFoco());
  clique("[data-be-pausa]", () => irParaPausaDoFoco());
  clique("[data-be-parar]", async () => {
    await fetch("/api/bemestar/parar", { method: "POST" });
    be.tarefa = "";
    mostrarFoco();
  });
  clique("[data-be-reiniciar]", async () => {
    await fetch("/api/bemestar/parar", { method: "POST" });
    comecarCicloDoFoco();
  });
  clique("[data-be-feito]", (b) => marcarLembreteFeito(Number(b.dataset.beFeito)));
  clique("[data-be-sugestao]", (b) => { const a = sugestaoParaAgora().acoes[Number(b.dataset.beSugestao)]; if (a) a.fazer(); });
  clique("[data-cfg-liga]", (b) => {
    const chave = b.dataset.cfgLiga;
    if (!chave.startsWith("lembrete:")) return;
    const l = (be.dados.lembretes || []).find((x) => x.id === Number(chave.split(":")[1]));
    if (l) guardarLembrete({ titulo: l.titulo, cada_min: l.cada_min, meta_dia: l.meta_dia, ligado: !l.ligado }, l.id);
  });
  clique("[data-be-editar]", (b) => {
    const l = (be.dados.lembretes || []).find((x) => x.id === Number(b.dataset.beEditar));
    if (l) { be.form = { id: l.id, titulo: l.titulo, cada_min: l.cada_min, meta_dia: l.meta_dia || "", ligado: l.ligado }; desenharFoco(); }
  });
  clique("[data-be-novo]", () => { be.form = { titulo: "", cada_min: 60, meta_dia: "", ligado: 1 }; desenharFoco(); const campo = document.querySelector('[data-be-campo="titulo"]'); if (campo) campo.focus(); });
  clique("[data-be-cancelar]", () => { be.form = null; desenharFoco(); });
  cada("[data-be-campo]", (el) => { el.oninput = () => { be.form[el.dataset.beCampo] = el.value; }; el.onchange = el.oninput; });
  clique("[data-be-guardar]", () => {
    const v = be.form;
    if (!v) return;
    guardarLembrete({ titulo: v.titulo, cada_min: Number(v.cada_min) || 60, meta_dia: Number(v.meta_dia) || 0, ligado: v.ligado !== 0 && v.ligado !== false }, v.id || null);
  });
  clique("[data-be-tirar]", async (b) => {
    if (!(await confirmar({ titulo: "Apagar este lembrete?", contexto: "Foco e bem-estar", texto: "Ele para de aparecer nas horas marcadas.", confirmar: "Apagar", perigo: true }))) return;
    await fetch("/api/bemestar/lembretes/" + b.dataset.beTirar, { method: "DELETE" });
    be.form = null;
    mostrarFoco();
  });
  clique("[data-be-inutil]", () => avisoCert("o parecer sai de regra sobre os totais da semana — ainda não há motor para aprender com o seu não"));
  clique("[data-be-agenda]", async () => {
    const p = parecerDaSemana();
    if (!p.sugestoes.length) return;
    let feitas = 0;
    for (const s of p.sugestoes) {
      const r = await fetch("/api/tarefas", { method: "POST", headers: BE_JSON, body: JSON.stringify({ dados: { titulo: s.tarefa, prazo: iso(new Date()), anotacao: s.texto } }) });
      if (r.ok) feitas += 1;
    }
    avisoCert(feitas ? plural(feitas, "tarefa criada", "tarefas criadas") + " para hoje — estão na Agenda, em Meu dia" : "não consegui criar as tarefas");
  });

  if (be.visao === "hoje" && be.dados.ciclo.estado !== "parado") be.relogio = setInterval(tiquetaqueDoFoco, 1000);
}

async function comecarCicloDoFoco() {
  const foco = document.querySelector("[data-be-foco]");
  const pausa = document.querySelector("[data-be-pausa-min]");
  const r = await fetch("/api/bemestar/ciclo", {
    method: "POST", headers: BE_JSON,
    body: JSON.stringify({ tarefa: be.tarefa || "", foco: foco ? Number(foco.value) : 0, pausa: pausa ? Number(pausa.value) : 0 }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  be.sugestaoDepois = false;
  mostrarFoco();
}

async function irParaPausaDoFoco() {
  await fetch("/api/bemestar/pausa", { method: "POST" });
  be.sugestaoDepois = false;
  mostrarFoco();
}

async function marcarLembreteFeito(id) {
  const r = await fetch("/api/bemestar/lembretes/" + id + "/feito", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  be.dados.lembretes = d.lembretes;
  be.dados.hoje = Object.assign({}, be.dados.hoje, d.hoje);
  desenharFoco();
}

async function guardarLembrete(dados, id) {
  if (!String(dados.titulo || "").trim()) { avisoCert("o lembrete precisa de um nome"); return; }
  const r = await fetch("/api/bemestar/lembretes", { method: "POST", headers: BE_JSON, body: JSON.stringify({ id: id || null, dados: dados }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  be.form = null;
  mostrarFoco();
}

function pararRelogioDoFoco() {
  if (be.relogio) clearInterval(be.relogio);
  be.relogio = null;
}

/* O relogio anda no navegador, mas quem manda e o servidor: a cada segundo
   ele diz quanto falta, e o anel acompanha. */
async function tiquetaqueDoFoco() {
  const alvo = $("be-relogio");
  if (!alvo) { pararRelogioDoFoco(); return; }
  let c;
  try { c = await (await fetch("/api/bemestar/ciclo")).json(); } catch (err) { return; }
  if (!$("be-relogio")) { pararRelogioDoFoco(); return; }
  alvo.textContent = c.restante_texto;
  const fase = $("be-fase");
  if (fase) fase.textContent = faseDoCiclo(c);
  const anel = $("be-anel");
  if (anel) anel.style.setProperty("--be-p", progressoDoCiclo(c) + "%");
  if (c.acabou) {
    pararRelogioDoFoco();
    avisoCert(c.estado === "foco" ? "ciclo de foco terminado — hora da pausa" : "pausa terminada — comece o próximo ciclo quando quiser");
    if (c.estado === "foco") { await irParaPausaDoFoco(); return; }
    mostrarFoco();
  }
}

