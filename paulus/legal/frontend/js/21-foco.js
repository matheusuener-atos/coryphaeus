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
    const [d, rel, t, av] = await Promise.all([
      fetch("/api/bemestar").then((r) => r.json()), pega("/api/relatorios"), pega("/api/tarefas?filtro=meu_dia"), pega("/api/avisos"),
    ]);
    be.avisos = av || { disponivel: false, ligado: false };
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

/* Uma coluna so, na largura util: o que era o painel da direita desce para
   baixo dos lembretes, em cartoes lado a lado. A coluna repetia a lista de
   lembretes (como interruptores) e enchia a tela de "em breve". */
function desenharFoco() {
  cabecalhoFoco();
  const miolo = be.visao === "semana" ? corpoDaSemana() : corpoDeHoje();
  $("centro").innerHTML = '<div class="acervo sem-painel be-tela" id="be-tela">' + miolo + "</div>";
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
    '<button class="com-icone' + (h.medindo ? "" : " primario") + '" data-be-medir="1">' + ic(h.medindo ? "visibility_off" : "visibility", 16) +
    (h.medindo ? "Desligar acompanhamento" : "Ligar acompanhamento") + "</button>";
  $("nav-tela").innerHTML = "";
}

/* ------------------------------------------------- o mostrador digital */
/* O relogio em sete segmentos, desenhado em SVG: nao depende de fonte
   baixada, fica nitido em qualquer tamanho e mostra os segmentos apagados
   bem de leve, como num relogio de verdade. A cor vem do texto (currentColor):
   tinta no foco, verde na pausa, clara no tema escuro. */

function beSegmento(x1, y1, x2, y2) {
  const m = 5, g = 1.6;   // meia espessura e a folga entre segmentos
  let pontos;
  if (y1 === y2) {
    const a = x1 + g, b = x2 - g;
    pontos = [[a, y1], [a + m, y1 - m], [b - m, y1 - m], [b, y1], [b - m, y1 + m], [a + m, y1 + m]];
  } else {
    const a = y1 + g, b = y2 - g;
    pontos = [[x1, a], [x1 + m, a + m], [x1 + m, b - m], [x1, b], [x1 - m, b - m], [x1 - m, a + m]];
  }
  return pontos.map((p) => p.join(",")).join(" ");
}

const BE_SEGMENTOS = {
  a: beSegmento(5, 5, 55, 5), b: beSegmento(55, 5, 55, 50), c: beSegmento(55, 50, 55, 95),
  d: beSegmento(5, 95, 55, 95), e: beSegmento(5, 50, 5, 95), f: beSegmento(5, 5, 5, 50), g: beSegmento(5, 50, 55, 50),
};
const BE_DIGITOS = {
  0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg",
};

function mostradorDigital(texto) {
  return [...String(texto)].map((ch) => {
    if (ch === ":") {
      return '<svg class="be-dois-pontos" viewBox="0 0 20 100" aria-hidden="true"><circle cx="10" cy="30" r="6"/><circle cx="10" cy="70" r="6"/></svg>';
    }
    const acesos = BE_DIGITOS[ch] || "";
    return '<svg class="be-digito" viewBox="0 0 60 100" aria-hidden="true">' + Object.entries(BE_SEGMENTOS).map(([s, pontos]) =>
      '<polygon points="' + pontos + '"' + (acesos.includes(s) ? "" : ' class="apagado"') + "/>").join("") + "</svg>";
  }).join("");
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
  return '<div class="acervo-principal">' + blocoDoCiclo() + cartaoDosLembretes() +
    '<div class="be-cartoes">' + cartaoDoRitmo() + cartaoDoDia() + cartaoDaSugestao() + "</div></div>";
}

/* O relogio, a barra de progresso e a barra das acoes do ciclo: iguais em
   Hoje e em Semana - o ciclo nao some porque a pessoa foi ver a semana. */
function blocoDoCiclo() {
  const d = be.dados;
  const c = d.ciclo;
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

  // De cima para baixo: o relogio no centro, solto na pagina - ele e a peca
  // de abertura -; a barra do ciclo, com os botoes e as escolhas; os
  // lembretes; e os cartoes do dia.
  const parado = c.estado === "parado" ? "" : " disabled";
  // O mostrador e quadrado, com os numeros grandes; o progresso e uma barra
  // deitada logo abaixo, da mesma largura. O --be-p fica no bloco de fora,
  // que o tiquetaque atualiza (id be-anel, o nome de quando era anel).
  const tempoNoMostrador = c.estado === "parado" ? String(c.foco_min).padStart(2, "0") + ":00" : c.restante_texto;
  const relogio = '<section class="be-relogio ' + classeAnel + '" id="be-anel" style="--be-p:' + progressoDoCiclo(c) + '%">' +
    '<div class="be-mostrador"><span class="be-tempo" id="be-relogio" role="timer" aria-label="' + esc(tempoNoMostrador) + '">' +
    mostradorDigital(tempoNoMostrador) + '</span><span class="be-fase" id="be-fase">' + esc(faseDoCiclo(c)) + "</span></div>" +
    '<div class="be-progresso" role="progressbar" aria-label="Progresso do ciclo"><i></i></div>' +
    '<span class="be-meta">' + esc(c.tarefa ? "tarefa deste ciclo: " + c.tarefa : "Ciclo de foco · sem tarefa marcada") + "</span></section>";
  const controles = '<div class="be-controles"><div class="be-botoes">' + botoes + "</div>" +
    '<div class="be-campos">' +
    '<label class="be-campo"><small>Foco</small><select data-be-foco="1"' + parado + ">" +
    [15, 25, 45, 50, 90].map((m) => '<option value="' + m + '"' + (c.foco_min === m ? " selected" : "") + ">" + m + " min</option>").join("") + "</select></label>" +
    '<label class="be-campo"><small>Pausa</small><select data-be-pausa-min="1"' + parado + ">" +
    [5, 10, 15].map((m) => '<option value="' + m + '"' + (c.pausa_min === m ? " selected" : "") + ">" + m + " min</option>").join("") + "</select></label>" +
    '<label class="be-campo"><small>Tarefa</small><select data-be-tarefa="1"' + parado + ">" + opcoes + "</select></label>" +
    "</div></div>";

  return relogio + controles;
}

/* Os lembretes de hoje, cada um com o seu interruptor: a coluna repetia a
   mesma lista so para ligar e desligar. Em "Ajustar", o mesmo cartao vira o
   editor. Restaurar o padrao fica sempre a vista - e a saida de quem se
   perdeu editando. */
function cartaoDosLembretes() {
  const d = be.dados;
  const lembretes = d.lembretes || [];
  const restaurar = '<button class="com-icone" data-be-restaurar="1">' + ic("restart_alt", 16) + "Restaurar padrão</button>";

  if (be.ajustando) {
    const v = be.form;
    let miolo;
    if (v) {
      miolo = '<div class="ag-form fin-form be-form">' +
        '<div class="ag-campo"><label>O que lembrar</label><input type="text" data-be-campo="titulo" value="' + esc(v.titulo || "") + '" placeholder="Beber água"></div>' +
        '<div class="ag-duas"><div class="ag-campo"><label>A cada</label><select data-be-campo="cada_min">' +
        [15, 20, 25, 30, 45, 60, 90, 120, 180, 240].map((m) => '<option value="' + m + '"' + (Number(v.cada_min) === m ? " selected" : "") + ">" + horasEmTexto(m) + "</option>").join("") + "</select></div>" +
        '<div class="ag-campo"><label>Meta por dia</label><input type="text" data-be-campo="meta_dia" value="' + esc(v.meta_dia || "") + '" placeholder="0 = sem meta"></div></div>' +
        '<div class="ag-form-rodape">' + (v.id ? '<button class="perigo" data-be-tirar="' + v.id + '">Apagar</button>' : "") +
        '<button data-be-cancelar="1">Cancelar</button><button class="primario" data-be-guardar="1">Guardar</button></div></div>';
    } else {
      // A MESMA LINHA do modo normal: o circulo guarda o lugar (sem ser
      // clicavel), o texto nao pula, o botao da direita vira Editar e o
      // interruptor fica onde esta. Apagar mora no formulario do Editar.
      miolo = '<div class="be-lembretes">' + (lembretes.map((l) =>
        '<div class="be-lembrete' + (l.ligado ? "" : " desligado") + '"><span class="be-marca vaga"></span>' +
        '<span class="duas-linhas"><b>' + esc(l.titulo) + '</b><small class="be-troca">a cada ' + esc(horasEmTexto(l.cada_min)) +
        (l.meta_dia ? " · meta " + l.meta_dia + " por dia" : " · sem meta") + "</small></span>" +
        '<button class="be-troca" data-be-editar="' + l.id + '">Editar</button>' + interruptorDoLembrete(l) + "</div>").join("") ||
        '<p class="rel-vazio">Nenhum lembrete.</p>') + "</div>";
    }
    return '<div class="fin-cartao be-cartao-lembretes"><div class="fin-cartao-cabeca"><span>' + (v ? (v.id ? "Editar lembrete" : "Novo lembrete") : "Lembretes de hoje") +
      '</span><small class="be-troca">editando · com “água” no nome, conta copos</small></div>' + miolo +
      (v ? "" : '<div class="be-rodape">' + restaurar +
        '<button class="primario com-icone be-troca" data-be-ajustar="1">' + ic("check", 16) + "Concluir</button>" +
        '<button class="com-icone be-troca" data-be-novo="1">' + ic("add", 16) + "Novo lembrete</button>" +
        '<span class="cresce"></span>' + interruptorDosAvisos() + "</div>") + "</div>";
  }

  // O circulo e de marcar: clicar registra o feito, como o botao. Ele fica
  // marcado enquanto o lembrete esta em dia - ate vencer o proximo
  // intervalo - e o dia todo quando a meta foi cumprida. Antes era so um
  // indicador da meta inteira, e parecia um botao que nao funcionava.
  const emDia = (l) => l.cumprido || feitoNoIntervalo(l);
  const marcados = lembretes.filter((l) => l.ligado && emDia(l)).length;
  const linhas = lembretes.map((l) => {
    const atrasado = l.ligado && !l.cumprido && l.atrasado_min > 0;
    const marcado = emDia(l);
    const classe = "be-lembrete" + (atrasado ? " atrasado" : "") + (l.ligado ? "" : " desligado");
    let sub;
    if (!l.ligado) sub = "desligado";
    else if (atrasado) sub = l.meta_texto + (l.meta_dia ? "" : " feito") + " · atrasado " + horasEmTexto(l.atrasado_min);
    else sub = "a cada " + horasEmTexto(l.cada_min) + (l.meta_dia ? " · " + l.meta_texto : "") + (l.proximo ? " · próximo às " + l.proximo : "");
    const agua = /água|agua/i.test(l.titulo);
    const circulo = marcado
      ? '<span class="be-marca on" title="' + (l.cumprido ? "Meta de hoje cumprida" : "Feito · volta às " + esc(horaDeVolta(l))) + '">' + ic("check", 12) + "</span>"
      : '<button class="be-marca" data-be-feito="' + l.id + '"' + (l.ligado ? "" : " disabled") + ' title="Marcar como feito" aria-label="Marcar ' + esc(l.titulo) + ' como feito"></button>';
    // Em dia, o botao some - a nao ser a agua, que pode ser mais de um copo.
    const botao = l.ligado && !l.cumprido && (!marcado || agua)
      ? '<button class="be-troca' + (atrasado ? " primario" : "") + '" data-be-feito="' + l.id + '">' + (agua ? "Bebi" : "Feito") + "</button>" : "";
    return '<div class="' + classe + '">' + circulo +
      '<span class="duas-linhas"><b>' + esc(l.titulo) + '</b><small class="be-troca' + (atrasado ? " acc" : "") + '">' + esc(sub) + "</small></span>" + botao +
      interruptorDoLembrete(l) + "</div>";
  }).join("");
  const ligados = lembretes.filter((l) => l.ligado).length;
  return '<div class="fin-cartao be-cartao-lembretes"><div class="fin-cartao-cabeca"><span>Lembretes de hoje</span><small class="be-troca">' + marcados + " de " + ligados + " em dia</small></div>" +
    '<div class="be-lembretes">' + (linhas || '<p class="rel-vazio">Nenhum lembrete. Crie um em Ajustar lembretes.</p>') + "</div>" +
    // Os botoes a esquerda; na ponta direita, o interruptor dos avisos, na
    // mesma coluna dos interruptores de cada lembrete.
    '<div class="be-rodape">' + restaurar + '<button class="com-icone be-troca" data-be-ajustar="1">' + ic("tune", 16) + "Ajustar lembretes</button>" +
    '<span class="cresce"></span>' + interruptorDosAvisos() + "</div></div>";
}

function interruptorDoLembrete(l) {
  return '<span class="interruptor-min' + (l.ligado ? " on" : "") + '" data-be-ligar="' + l.id + '" role="switch" aria-checked="' + Boolean(l.ligado) +
    '" title="' + (l.ligado ? "Desligar" : "Ligar") + ' este lembrete"><span class="chave"></span></span>';
}

/* Entrar e sair de "Ajustar" (e abrir o formulario) sem salto: a altura do
   cartao vai da antiga para a nova, e o que trocou de texto entra num
   esmaecer curto. Com "Animacoes reduzidas", troca direto. */
function trocarLembretes(mudar) {
  const antes = document.querySelector(".be-cartao-lembretes");
  const altura = antes ? antes.offsetHeight : 0;
  mudar();
  desenharFoco();
  const cartao = document.querySelector(".be-cartao-lembretes");
  if (!cartao || !animacoesLigadas()) return;
  const nova = cartao.offsetHeight;
  if (altura && altura !== nova) {
    cartao.style.overflow = "hidden";
    cartao.animate([{ height: altura + "px" }, { height: nova + "px" }], { duration: 280, easing: "cubic-bezier(.2,.7,.3,1)" })
      .onfinish = () => { cartao.style.overflow = ""; };
  }
  cartao.querySelectorAll(".be-troca, .be-form").forEach((el) => {
    el.animate([{ opacity: 0, transform: "translateY(3px)" }, { opacity: 1, transform: "none" }], { duration: 240, easing: "ease-out" });
  });
}

/* Quando o lembrete volta a pedir: a ultima vez mais o intervalo. */
function horaDeVolta(l) {
  if (l.proximo) return l.proximo;
  const quando = new Date(String(l.ultima_vez || "").replace(" ", "T"));
  if (isNaN(quando)) return "";
  const volta = new Date(quando.getTime() + (l.cada_min || 60) * 60000);
  return String(volta.getHours()).padStart(2, "0") + ":" + String(volta.getMinutes()).padStart(2, "0");
}

/* Feito dentro do intervalo de agora: a ultima vez foi ha menos de
   `cada_min`. O servidor grava a hora local ("2026-09-25 14:05:00"). */
function feitoNoIntervalo(l) {
  if (!l.ultima_vez) return false;
  const quando = new Date(String(l.ultima_vez).replace(" ", "T"));
  if (isNaN(quando) || quando.toDateString() !== new Date().toDateString()) return false;
  return Date.now() - quando.getTime() < (l.cada_min || 60) * 60000;
}

/* Os avisos do Windows (src/avisos.py): a notificacao do canto da tela e o
   botao piscando na barra de tarefas. So aparece onde existe. */
function interruptorDosAvisos() {
  const a = be.avisos || {};
  if (!a.disponivel) return "<span>Ficam nesta máquina · nada é compartilhado</span>";
  return '<span class="be-avisos" data-be-avisos="1" role="switch" aria-checked="' + Boolean(a.ligado) + '" title="A notificação do Windows e o botão piscando na barra de tarefas">' +
    "<span>Avisar no Windows" + (a.ligado ? "" : " · desligado") + "</span>" +
    '<span class="interruptor-min' + (a.ligado ? " on" : "") + '"><span class="chave"></span></span></span>';
}

/* Tarefas concluidas por hora, de hoje. */
function cartaoDoRitmo() {
  const d = be.dados;
  const h = d.hoje;
  const c = d.ciclo;
  const porHora = feitasPorHora();
  const teto = Math.max(1, ...porHora);
  const agora = new Date().getHours();
  const total = porHora.reduce((s, x) => s + x, 0);
  const barras = BE_HORAS.map((hora, i) => {
    const classe = porHora[i] ? (hora === agora ? "agora" : "") : "vazia";
    return '<span class="' + classe + '" title="' + hora + 'h · ' + esc(plural(porHora[i], "tarefa concluída", "tarefas concluídas")) + '" style="height:' +
      (porHora[i] ? Math.max(8, Math.round(porHora[i] * 100 / teto)) : 2) + '%"></span>';
  }).join("");
  let leitura = total
    ? "Você concluiu mais por volta das " + BE_HORAS[porHora.indexOf(Math.max(...porHora))] + "h."
    : "Nenhuma tarefa concluída hoje ainda.";
  if (h.medindo && h.sem_pausa_min >= 60) leitura += " Está sem pausa há " + horasEmTexto(h.sem_pausa_min) + (c.estado === "foco" ? " — a próxima cai no fim deste ciclo." : ".");
  else if (c.estado === "foco") leitura += " A próxima pausa cai em " + horasEmTexto(Math.ceil(c.restante / 60)) + ", no fim deste ciclo.";
  return '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Seu ritmo hoje</span><small>tarefas concluídas por hora</small></div>' +
    '<div class="be-ritmo"><div class="be-horas">' + barras + "</div>" +
    '<div class="be-horas-rotulos">' + BE_HORAS.map((x) => "<span>" + x + "h</span>").join("") + "</div>" +
    "<p>" + esc(leitura) + "</p></div></div>";
}

/* Os numeros do dia. A agua nao entra: ja esta no lembrete de beber agua. */
function cartaoDoDia() {
  const h = be.dados.hoje;
  const t = (((be.rel || {}).dia) || {}).tarefas || { feitas: [], planejado: 0 };
  const medido = h.medindo || h.minutos_ativos;
  return '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Hoje</span><small>' + (h.medindo ? "medindo" : "sem medição") + "</small></div>" +
    '<div class="cfg-chaves be-chaves">' +
    chaveCfg("Tempo ativo", medido ? h.ativo_texto : "sem medição", medido ? "" : "mute") +
    chaveCfg("Ciclos de foco", String(h.ciclos || 0)) +
    chaveCfg("Pausas feitas", String(h.pausas || 0)) +
    chaveCfg("Tarefas concluídas", t.feitas.length + (t.planejado ? " de " + t.planejado : "")) +
    chaveCfg("Maior sequência sem pausa", h.seguida_texto) + "</div></div>";
}

function cartaoDaSugestao() {
  const s = sugestaoParaAgora();
  return '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Sugestão para agora</span><small>pelo que foi medido</small></div>' +
    '<div class="be-sugestao">' + ic("self_improvement", 18) + "<span><span>" + esc(s.texto) + "</span>" +
    (s.acoes.length ? '<span class="fin-pede-acoes">' + s.acoes.map((a, j) =>
      '<button class="' + (a.primario ? "primario" : "") + '" data-be-sugestao="' + j + '">' + esc(a.rotulo) + "</button>").join("") + "</span>" : "") +
    "</span></div></div>";
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

/* Quem editou demais - apagou o de beber agua, trocou os tempos, criou seis
   parecidos - volta para a lista de fabrica. Pergunta antes, porque apaga os
   que estao la. */
async function restaurarLembretes() {
  const quantos = (be.dados.lembretes || []).length;
  const certo = await confirmar({
    titulo: "Restaurar os lembretes padrão?",
    contexto: "Foco e bem-estar",
    texto: (quantos ? "Os " + plural(quantos, "lembrete") + " de agora saem da lista e voltam os quatro do começo — beber água, levantar e caminhar, olhar para longe e alongar." : "Voltam os quatro do começo: beber água, levantar e caminhar, olhar para longe e alongar.") +
      "\nO que já foi medido (copos, pausas, ciclos) fica.",
    confirmar: "Restaurar",
    perigo: true,
  });
  if (!certo) return;
  const r = await fetch("/api/bemestar/lembretes/restaurar", { method: "POST" });
  if (!r.ok) { avisoCert("não consegui restaurar: " + await erroDe(r)); return; }
  be.form = null;
  await mostrarFoco();
  avisoCert("lembretes padrão de volta", { tom: "ok" });
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

  // BARRAS DEITADAS, DE PONTA A PONTA. Em pe e dentro de um cartao, um dia
  // com 1,7 h virava uma torre no vazio e os outros seis sumiam; deitadas, o
  // dia e o numero se leem na mesma linha e a semana cabe em sete linhas.
  const barras = dias.map((x) => {
    const minutos = x.minutos_ativos || 0;
    const classe = "be-barra" + (x.dia === hoje ? " hoje" : "") + (minutos ? "" : " vazio");
    return '<div class="' + classe + '"><span>' + esc(maiuscula(x.rotulo)) + "</span>" +
      '<i><b style="width:' + (minutos ? Math.max(2, Math.round(minutos * 100 / teto)) : 0) + '%"></b></i>' +
      "<small>" + esc(minutos ? horasCurtas(minutos) : "—") + (x.pausas ? " · " + plural(x.pausas, "pausa") : "") + "</small></div>";
  }).join("");

  // Em cartao, como o de Habitos ao lado: os dois dividem a linha.
  const foco = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Foco na semana</span><small>' +
    esc(dataCurta(s.de) + " a " + dataCurta(s.ate) + " · " + horasEmTexto(total)) + "</small></div>" +
    '<section class="be-semana"><div class="be-barras">' + barras + "</div>" +
    '<div class="be-semana-somas"><div><small>Média por dia medido</small><b>' + esc(comDado.length ? horasEmTexto(media) : "—") + "</b></div>" +
    "<div><small>Dia mais ativo</small><b>" + esc(melhor ? maiuscula(melhor.rotulo) + " · " + horasEmTexto(melhor.minutos_ativos) : "—") + "</b></div>" +
    "<div><small>Pausas feitas</small><b>" + esc(s.pausas + " em " + plural(s.ciclos, "ciclo")) + "</b></div></div>" +
    (s.tem_dado ? "" : '<p class="cfg-explica">Nenhum dia com medição nesta semana. Ligue o acompanhamento e a semana aparece aqui — sem isso, qualquer gráfico seria invenção.</p>') +
    "</section></div>";

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

  // O ciclo continua em cima, como em Hoje; o grafico e os habitos lado a
  // lado; o parecer embaixo, na largura toda.
  return '<div class="acervo-principal be-semana-tela">' + blocoDoCiclo() +
    '<div class="be-duas">' + foco + habitos + "</div>" + cartaoDoParecer() + "</div>";
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

/* O parecer da semana, em cartao ao lado das barras. A semana anterior
   entra como uma linha no cabecalho, e nao como mais um bloco. */
function cartaoDoParecer() {
  const s = be.dados.semana;
  const p = parecerDaSemana();
  const antes = be.semanaAntes;
  const totalAntes = antes ? minutosDaSemana(antes) : null;
  const variacao = totalAntes === null ? null : minutosDaSemana(s) - totalAntes;
  const comparado = totalAntes === null ? "só com dados locais"
    : "semana anterior " + horasEmTexto(totalAntes) + " · " + (variacao >= 0 ? "+ " : "− ") + horasEmTexto(Math.abs(variacao));
  return '<div class="fin-cartao be-parecer"><div class="fin-cartao-cabeca"><span>Parecer da semana</span><small>' + esc(comparado) + "</small></div>" +
    '<div class="fin-parecer solto"><p class="fin-lead">' + esc(p.lead) + "</p><p>" + esc(p.resto) + "</p></div>" +
    (p.sugestoes.length
      ? '<div class="fin-sugestoes be-sugestoes">' + p.sugestoes.map((x) => '<div class="fin-sugestao"><i></i><span>' + esc(x.texto) + "</span></div>").join("") + "</div>" +
        '<div class="be-rodape"><button class="em-ligacao" data-be-inutil="1">Não foi útil</button><span class="cresce"></span>' +
        '<button class="primario com-icone" data-be-agenda="1">' + ic("calendar_month", 16) + "Aplicar na Agenda</button></div>"
      : "") + "</div>";
}

/* ------------------------------------------------------------ as acoes */

function ligarFoco() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });

  clique("[data-be-visao]", (b) => { be.visao = b.dataset.beVisao; be.ajustando = false; be.form = null; mostrarFoco(); });
  clique("[data-be-ajustar]", () => {
    if (be.visao !== "hoje") { be.ajustando = true; be.form = null; be.visao = "hoje"; mostrarFoco(); return; }
    trocarLembretes(() => { be.ajustando = !be.ajustando; be.form = null; });
  });
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
  clique("[data-be-avisos]", async () => {
    const ligar = !(be.avisos && be.avisos.ligado);
    const r = await fetch("/api/preferencias", { method: "POST", headers: BE_JSON, body: JSON.stringify({ avisos_windows: ligar }) });
    if (!r.ok) { avisoCert("não consegui gravar: " + await erroDe(r)); return; }
    be.avisos = Object.assign({}, be.avisos, { ligado: ligar });
    desenharFoco();
    if (!ligar) { avisoCert("avisos do Windows desligados — os lembretes seguem só nesta tela"); return; }
    // Ligar manda um aviso de verdade: e o jeito de a pessoa ver onde ele cai.
    const t = await fetch("/api/avisos/teste", { method: "POST" }).then((x) => x.json()).catch(() => ({ ok: false }));
    avisoCert(t.ok ? "avisos ligados — mandei um de teste para o canto da tela" : "liguei, mas o Windows não mostrou o aviso de teste");
  });
  clique("[data-be-ligar]", (b) => {
    const l = (be.dados.lembretes || []).find((x) => x.id === Number(b.dataset.beLigar));
    if (l) guardarLembrete({ titulo: l.titulo, cada_min: l.cada_min, meta_dia: l.meta_dia, ligado: !l.ligado }, l.id);
  });
  clique("[data-be-editar]", (b) => {
    const l = (be.dados.lembretes || []).find((x) => x.id === Number(b.dataset.beEditar));
    if (l) trocarLembretes(() => { be.form = { id: l.id, titulo: l.titulo, cada_min: l.cada_min, meta_dia: l.meta_dia || "", ligado: l.ligado }; });
  });
  clique("[data-be-restaurar]", () => restaurarLembretes());
  clique("[data-be-novo]", () => {
    trocarLembretes(() => { be.form = { titulo: "", cada_min: 60, meta_dia: "", ligado: 1 }; });
    const campo = document.querySelector('[data-be-campo="titulo"]');
    if (campo) campo.focus();
  });
  clique("[data-be-cancelar]", () => trocarLembretes(() => { be.form = null; }));
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

  // Cada redesenho liga o tiquetaque de novo: desliga o anterior antes, ou
  // eles se acumulam (um por abrir e fechar o Ajustar, por exemplo).
  pararRelogioDoFoco();
  if (be.dados.ciclo.estado !== "parado") be.relogio = setInterval(tiquetaqueDoFoco, 1000);
}

/* Ctrl+Shift+F de qualquer tela: comeca o ciclo, ou vai para a pausa se ele
   ja estiver correndo. Abre o Foco junto - mexer no relogio de alguem sem
   mostrar o relogio seria mexer as escondidas. */
async function alternarFocoPorAtalho() {
  let ciclo = ((be.dados || {}).ciclo) || null;
  if (!ciclo) {
    try { ciclo = (await (await fetch("/api/bemestar")).json()).ciclo; } catch (err) { ciclo = null; }
  }
  if (ciclo && ciclo.estado === "foco") await irParaPausaDoFoco();
  else await comecarCicloDoFoco();
  marcarDestino("foco");
  await mostrarFoco("hoje");
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
  if (alvo.getAttribute("aria-label") !== c.restante_texto) {
    alvo.innerHTML = mostradorDigital(c.restante_texto);
    alvo.setAttribute("aria-label", c.restante_texto);
  }
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

