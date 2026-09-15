/* ----------------------------------------------------------- servicos */
/*
   Servicos (docs/ui/03-telas-desktop.md, A15): a grade de pastas e, dentro
   de cada uma, a visao de trabalho - Resumo da IA, etapas, arquivos - com o
   painel de equipe, prazos, anotacoes e trilha. O servidor guarda a pasta
   (src/servicos.py); os arquivos sao vinculos ao Acervo, os prazos vem da
   Agenda pelo cliente e a equipe vem de Cadastros. O resumo e escrito pelo
   modelo local sobre o que esta gravado; sem modelo, a tela diz isso.
*/

const SV_JSON = { "Content-Type": "application/json" };

const sv = {
  visao: "pastas", filtro: "andamento", termo: "", lista: [], contagem: {}, status: [], clientes: [],
  aberto: null, acervo: null, largo: false,
  pedindo: false, salvando: false, escolhidos: new Set(), conversando: null, arquivosAbertos: false,
};

async function mostrarServicos(visao) {
  if (visao) sv.visao = visao;
  if (sv.visao === "trabalho" && !sv.aberto) sv.visao = "pastas";
  abrirTela("Serviços", { cheia: true });
  marcarDestino("servicos");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  atualizarPostura();
  try {
    const pedidos = [fetch("/api/servicos?filtro=" + encodeURIComponent(sv.filtro) + "&termo=" + encodeURIComponent(sv.termo)).then((r) => r.json())];
    if (sv.visao === "trabalho") {
      pedidos.push(fetch("/api/servicos/" + sv.aberto.id).then((r) => (r.ok ? r.json() : null)));
      pedidos.push(sv.acervo ? Promise.resolve(null) : fetch("/api/biblioteca").then((r) => r.json()));
    }
    const [d, s, b] = await Promise.all(pedidos);
    sv.lista = d.servicos || [];
    sv.contagem = d.contagem || {};
    sv.status = d.status || [];
    sv.clientes = d.clientes || [];
    if (b) sv.acervo = b.documentos || [];
    if (sv.visao === "trabalho") {
      if (s) sv.aberto = s;
      else { sv.aberto = null; sv.visao = "pastas"; avisoCert("esse serviço não existe mais"); }
    }
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharServicos();
}

async function abrirServico(id) {
  sv.aberto = { id: id };
  sv.arquivosAbertos = false;
  await mostrarServicos("trabalho");
}

/* Depois de uma mexida na pasta aberta: busca so ela e redesenha. */
async function recarregarServico() {
  if (!sv.aberto) return;
  const r = await fetch("/api/servicos/" + sv.aberto.id);
  if (!r.ok) { sv.aberto = null; return mostrarServicos("pastas"); }
  sv.aberto = await r.json();
  desenharServicos();
}

function desenharServicos() {
  cabecalhoServicos();
  let html;
  if (sv.visao === "trabalho") {
    const classe = "acervo sv-tela" + (sv.largo ? " painel-largo" : "");
    html = '<div class="' + classe + '" id="sv-tela">' + corpoDoTrabalho() + painelDoTrabalho() + "</div>";
  } else {
    const classe = "acervo sv-tela sem-painel";
    html = '<div class="' + classe + '" id="sv-tela">' + corpoDasPastas() + "</div>";
  }
  $("centro").innerHTML = html;
  ligarServicos();
  atualizarPostura();
}

/* ------------------------------------------------------ o cabecalho */

function cabecalhoServicos() {
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  const nav = $("nav-tela");
  const botao = (chave, v, r) => {
    const classe = v === sv[chave] ? "ativa" : "";
    return '<button class="' + classe + '" data-sv-' + chave + '="' + v + '">' + r + "</button>";
  };
  if (sv.visao === "trabalho" && sv.aberto) {
    const s = sv.aberto;
    nav.innerHTML = '<button class="voltar" data-sv-voltar="1" title="Voltar às pastas" aria-label="Voltar às pastas">' + ic("arrow_back", 18) + "</button>";
    titulo.textContent = s.nome;
    // O nome da pasta se renomeia clicando nele, como o de uma conversa.
    titulo.classList.add("renomeavel");
    titulo.title = "Clique para renomear";
    renomeadorDoTitulo = { limite: 80, guardar: (novo) => renomearServico(s, novo) };
    meta.textContent = (s.cliente_nome ? s.cliente_nome + " · " : "") + s.status_rotulo + " · " + s.progresso + "%";
    $("acoes-tela").innerHTML =
      '<button class="com-icone" data-sv-editar="1">' + ic("edit", 16) + "Editar</button>" +
      (s.status === "concluido"
        ? '<button class="com-icone" data-sv-status="andamento">' + ic("restart_alt", 16) + "Reabrir serviço</button>"
        : '<button class="com-icone" data-sv-status="concluido">' + ic("task_alt", 16) + "Concluir serviço</button>");
    return;
  }
  nav.innerHTML = "";
  titulo.textContent = "Serviços";
  titulo.classList.remove("renomeavel");
  titulo.removeAttribute("title");
  renomeadorDoTitulo = null;
  const c = sv.contagem;
  meta.textContent = (c.andamento || 0) + " em andamento · " + (c.aguardando || 0) + " aguardando cliente · " + (c.concluidos || 0) + " concluídos";
  $("acoes-tela").innerHTML =
    '<label class="busca-tela">' + ic("search", 18) + '<input type="text" id="sv-busca" placeholder="Buscar serviços…" value="' + esc(sv.termo) + '"></label>' +
    '<div class="visoes">' + botao("filtro", "andamento", "Em andamento") + botao("filtro", "todos", "Todos") + botao("filtro", "concluidos", "Concluídos") + "</div>" +
    '<button class="primario com-icone" data-sv-novo="1">' + ic("add", 16) + "Novo serviço</button>";
}

/* --------------------------------------------------------- as pastas */

function corpoDasPastas() {
  const cartoes = sv.lista.map(cartaoDoServico).join("");
  for (const id of [...sv.escolhidos]) if (!sv.lista.some((s) => String(s.id) === id)) sv.escolhidos.delete(id);
  const barra = sv.escolhidos.size
    ? '<div class="barra-selecao">' + barraDeSelecao(sv.escolhidos.size, false,
      '<button data-sv-sel-concluir="1">' + ic("task_alt", 16) + "Concluir</button><span class=\"divisa-v\"></span>" +
      '<button class="botao-icone perigo" data-sv-sel-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-sv-sel-limpar") + "</div>"
    : "";
  return '<div class="acervo-principal">' + barra + '<div class="sv-grade">' + (sv.lista.length ? "" : vazioDosServicos()) + cartoes +
    '<button class="sv-novo" data-sv-novo="1">' + ic("add", 20) + "<b>Novo serviço</b><small>ou peça ao Assistente: “abra um serviço para…”</small></button>" +
    "</div></div>";
}

function vazioDosServicos() {
  let h3, p;
  if (sv.termo) { h3 = "Nada com “" + esc(sv.termo) + "”"; p = "Procurei no nome, na descrição e no cliente."; }
  else if (sv.filtro === "concluidos") { h3 = "Nenhum serviço concluído"; p = "Quando uma pasta chega ao fim, Concluir serviço traz ela para cá — com a trilha inteira guardada."; }
  else if (sv.contagem.total) { h3 = "Nada em andamento"; p = "Todas as pastas estão concluídas. Abra uma nova ou veja Todos."; }
  else { h3 = "Nenhum serviço ainda"; p = "Um serviço é a pasta de trabalho de um assunto: nome próprio, cliente, o que está sendo feito, as etapas, quem cuida, os arquivos do Acervo, os prazos e a trilha do que aconteceu. Abra a primeira pelo cartão ao lado."; }
  return '<div class="sv-vazio"><h3>' + h3 + "</h3><p>" + p + "</p></div>";
}

function cartaoDoServico(s) {
  const classe = "sv-pasta" + (s.status === "concluido" ? " feita" : "") + (sv.escolhidos.has(String(s.id)) ? " escolhida" : "");
  const sub = (s.cliente_nome || "sem cliente") + (tipoDoDocumentoSv(s.cliente_documento) ? " · " + tipoDoDocumentoSv(s.cliente_documento) : "");
  const proximo = proximoDoServico(s);
  const classeProximo = "sv-proximo" + (proximo && proximo.atrasado ? " atrasado" : "");
  return '<div class="' + classe + '" data-sv-abrir="' + s.id + '" data-sel="' + s.id + '">' +
    '<div class="sv-pasta-cabeca">' + ic("folder", 20) + '<div class="duas-linhas"><b>' + esc(s.nome) + "</b><small>" + esc(sub) + "</small></div>" +
    '<button class="mais-linha" data-sv-mais="' + s.id + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>" +
    "<p>" + esc(s.descricao || "Sem descrição ainda — abra a pasta e escreva o que está sendo feito.") + "</p>" +
    '<div class="sv-pasta-pe">' + seloDoStatusSv(s) + '<b class="sv-pct">' + s.progresso + "%</b>" +
    (s.equipe.length ? '<span class="sv-avatares">' + s.equipe.slice(0, 3).map((p) =>
      '<span class="cad-avatar" title="' + esc(p.nome) + '">' + esc(iniciaisDoRemetente(p.nome)) + "</span>").join("") + "</span>" : "") +
    "<span>" + plural(s.arquivos_quantos, "arquivo") + " · " + plural(s.prazos_quantos, "prazo") + "</span>" +
    (proximo ? '<span class="' + classeProximo + '">' + ic("event_upcoming", 16) + esc(proximo.texto) + "</span>" : "") +
    "</div></div>";
}

/* Concluído em verde e suspenso em vinho: os dois estados que mudam o que
   se faz com a pasta saltam da grade. */
function seloDoStatusSv(s) {
  const classe = "fin-status sv-status-" + (s.status || "andamento");
  return '<span class="' + classe + '">' + esc(s.status_rotulo) + "</span>";
}

function tipoDoDocumentoSv(documento) {
  const n = String(documento || "").replace(/\D/g, "").length;
  if (n === 14) return "pessoa jurídica";
  if (n > 0 && n <= 11) return "pessoa física";
  return "";
}

/* O proximo prazo ou compromisso do cliente: o que o cartao mostra no pe. */
function proximoDoServico(s) {
  const c = s.proximo_compromisso;
  const candidatos = [];
  if (s.proximo_prazo) candidatos.push({ quando: s.proximo_prazo, rotulo: "" });
  if (c) candidatos.push({ quando: c.data, rotulo: c.tipo && c.tipo !== "compromisso" ? c.tipo : "" });
  if (!candidatos.length) return null;
  candidatos.sort((a, b) => a.quando.localeCompare(b.quando));
  const x = candidatos[0];
  const dias = diasAte(x.quando);
  let texto = dataCurta(x.quando);
  if (dias === 0) texto = "hoje · " + texto;
  else if (dias === 1) texto = "amanhã · " + texto;
  else if (dias < 0) texto += " · atrasado";
  return { texto: (x.rotulo ? x.rotulo + " " : "") + texto, atrasado: dias < 0 };
}

function diasAte(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!m) return 9999;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  return Math.round((d - hoje) / 86400000);
}

/* "hoje 09:47", "ontem 17:50", "18 ago", "5 set 2025". */
function quandoCurtoSv(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso.slice(0, 10);
  const hoje = new Date();
  const dias = -diasAte(iso.slice(0, 10));
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  if (dias === 0) return "hoje " + hora;
  if (dias === 1) return "ontem " + hora;
  const base = d.getDate() + " " + MESES_CURTOS[d.getMonth()];
  return d.getFullYear() === hoje.getFullYear() ? base : base + " " + d.getFullYear();
}

function haQuantoSv(iso) {
  const ms = Date.now() - new Date(iso);
  if (isNaN(ms)) return "";
  const min = Math.round(ms / 60000);
  if (min < 1) return "agora";
  if (min < 60) return "há " + min + " min";
  const h = Math.round(min / 60);
  if (h < 24) return "há " + h + " h";
  return quandoCurtoSv(iso);
}

/* ------------------------------------------------ a visao de trabalho */

/* A PASTA ABERTA. No centro, o histórico: o que aconteceu no serviço em
   ordem, do começo até agora — criado, documentos anexados (em lista),
   etapas (com a marca de concluir), anotações, resumos e as perguntas feitas
   aqui, com a resposta. Embaixo dele, os comandos prontos e uma caixa de
   pedido pequena para conversar sobre a pasta. Depois, os arquivos, com
   "Ver mais" como no Assistente. O painel traz equipe, etapas, prazos e
   anotações. */
function corpoDoTrabalho() {
  const s = sv.aberto;
  return '<div class="acervo-principal sv-principal">' + cartaoDoHistorico(s) + cartaoDosArquivos(s) + "</div>";
}

/* Eventos antigos só tinham texto: o começo diz o que eram. */
const COMECOS_DA_TRILHA = [
  ["Serviço aberto", "criado"], ["Arquivo ligado: ", "arquivo"], ["Arquivo desligado: ", "arquivo_desligado"],
  ["Etapa adicionada: ", "etapa"], ["Etapa concluída: ", "etapa_feita"], ["Etapa reaberta: ", "etapa_reaberta"],
  ["Etapa removida: ", "etapa_removida"], ["Anotação: ", "anotacao"], ["Resumo escrito", "resumo"],
  ["Status: ", "status"], ["Equipe: ", "equipe"], ["Pergunta: ", "conversa"],
];

function eventosDoHistorico(s) {
  const saida = [];
  s.trilha.slice().reverse().forEach((e) => {
    let tipo = e.tipo;
    let dados = e.dados || null;
    if (!tipo) {
      const achado = COMECOS_DA_TRILHA.find(([comeco]) => e.texto.startsWith(comeco));
      tipo = achado ? achado[1] : "texto";
      if (achado && !dados) {
        const resto = e.texto.slice(achado[0].length).trim();
        dados = { nome: resto, titulo: resto, texto: resto };
      }
    }
    dados = dados || {};
    // Documentos anexados no mesmo dia viram uma lista só.
    const anterior = saida[saida.length - 1];
    if (tipo === "arquivo" && anterior && anterior.tipo === "arquivo" && anterior.quando.slice(0, 10) === e.quando.slice(0, 10)) {
      anterior.itens.push(dados);
      return;
    }
    saida.push({ tipo: tipo, quando: e.quando, quem: e.quem, texto: e.texto, dados: dados, itens: tipo === "arquivo" ? [dados] : null });
  });
  return saida;
}

function linhaDoHistorico(icone, titulo, ev, extra) {
  const quando = quandoCurtoSv(ev.quando) + (ev.quem ? " · " + ev.quem : "");
  const classe = "sv-ev sv-ev-" + ev.tipo;
  return '<div class="' + classe + '"><span class="sv-ev-ic">' + ic(icone, 16) + "</span>" +
    '<div class="sv-ev-corpo"><div class="sv-ev-topo"><b>' + esc(titulo) + "</b><small>" + esc(quando) + "</small></div>" +
    (extra || "") + "</div></div>";
}

function eventoDoHistorico(ev, s, usadas, ultimoResumo) {
  const d = ev.dados;
  switch (ev.tipo) {
    case "criado": {
      const resto = ev.texto.replace(/^Serviço aberto\s*/, "");
      return linhaDoHistorico("create_new_folder", "Serviço criado", ev, resto ? '<p class="sv-ev-texto">' + esc(maiuscula(resto)) + "</p>" : "");
    }
    case "arquivo": {
      const linhas = ev.itens.map((a) => {
        const noAcervo = (sv.acervo || []).some((x) => x.sha1 === a.sha1) || (s.arquivos || []).some((x) => x.sha1 === a.sha1 || x.nome === a.nome);
        const alvo = a.sha1 ? ' data-sv-arquivo="' + esc(a.sha1) + '"' : "";
        return '<button type="button" class="sv-ev-doc"' + alvo + (noAcervo && a.sha1 ? "" : " disabled") + ">" + glifo(a.nome) +
          '<span class="corta">' + esc(a.nome) + "</span></button>";
      }).join("");
      const titulo = ev.itens.length === 1 ? "Documento anexado" : plural(ev.itens.length, "documento anexado", "documentos anexados");
      return linhaDoHistorico("attach_file", titulo, ev, '<div class="sv-ev-docs">' + linhas + "</div>");
    }
    case "etapa": {
      const i = s.etapas.findIndex((e, k) => e.titulo === d.titulo && !usadas.has(k));
      if (i < 0) return linhaDoHistorico("add_task", "Etapa adicionada", ev, '<p class="sv-ev-texto riscado">' + esc(d.titulo) + " · removida depois</p>");
      usadas.add(i);
      const e = s.etapas[i];
      const classe = "sv-ev-tarefa" + (e.feita ? " feita" : "");
      return linhaDoHistorico("add_task", "Etapa adicionada", ev,
        '<button type="button" class="' + classe + '" data-sv-etapa="' + i + '" title="' + (e.feita ? "Reabrir" : "Marcar como concluída") + '">' +
        ic(e.feita ? "check_circle" : "radio_button_unchecked", 20) + '<span class="duas-linhas"><b>' + esc(e.titulo) + "</b>" + subDaEtapa(e) + "</span></button>");
    }
    case "etapa_feita": return linhaDoHistorico("task_alt", "Etapa concluída: " + d.titulo, ev);
    case "etapa_reaberta": return linhaDoHistorico("replay", "Etapa reaberta: " + d.titulo, ev);
    case "etapa_removida": return linhaDoHistorico("remove_circle_outline", "Etapa removida: " + d.titulo, ev);
    case "arquivo_desligado": return linhaDoHistorico("link_off", "Documento desligado: " + d.nome, ev);
    case "anotacao": return linhaDoHistorico("edit_note", "Anotação", ev, '<p class="sv-ev-citacao">' + esc(d.texto) + "</p>");
    case "resumo": {
      const texto = d.texto || (ultimoResumo ? s.resumo : "");
      return linhaDoHistorico("auto_awesome", "Resumo do assistente", ev, texto ? '<p class="sv-ev-resposta">' + esc(texto) + "</p>" : "");
    }
    case "conversa":
      return linhaDoHistorico("forum", "Pergunta sobre o serviço", ev,
        '<p class="sv-ev-pergunta">' + esc(d.pergunta || d.texto || "") + "</p>" +
        (d.resposta ? '<p class="sv-ev-resposta">' + esc(d.resposta) + "</p>" : ""));
    case "status": return linhaDoHistorico("flag", ev.texto, ev);
    case "equipe": return linhaDoHistorico("group", ev.texto, ev);
    default: return linhaDoHistorico("history", ev.texto, ev);
  }
}

function cartaoDoHistorico(s) {
  const eventos = eventosDoHistorico(s);
  const usadas = new Set();
  const ultimoResumo = eventos.map((e) => e.tipo).lastIndexOf("resumo");
  let linhas = eventos.map((ev, i) => eventoDoHistorico(ev, s, usadas, i === ultimoResumo)).join("");
  // O que está sendo pedido agora entra no fim, andando.
  if (sv.conversando) {
    linhas += '<div class="sv-ev sv-ev-conversa pendente"><span class="sv-ev-ic">' + ic("forum", 16) + "</span>" +
      '<div class="sv-ev-corpo"><div class="sv-ev-topo"><b>Pergunta sobre o serviço</b><small>agora</small></div>' +
      '<p class="sv-ev-pergunta">' + esc(sv.conversando.pergunta) + "</p>" +
      '<p class="sv-ev-pensando">' + coroa(16) + '<span data-sv-pensando="' + sv.conversando.desde + '">pensando…</span></p></div></div>';
  }
  if (sv.pedindo) {
    linhas += '<div class="sv-ev sv-ev-resumo pendente"><span class="sv-ev-ic">' + ic("auto_awesome", 16) + "</span>" +
      '<div class="sv-ev-corpo"><div class="sv-ev-topo"><b>Resumo do assistente</b><small>agora</small></div>' +
      '<p class="sv-ev-pensando">' + coroa(16) + '<span data-sv-pensando="' + (sv.pedindoDesde || Date.now()) + '">lendo o que está gravado na pasta…</span></p></div></div>';
  }
  const ocupado = Boolean(sv.conversando || sv.pedindo);
  const comando = (chave, icone, rotulo) => '<button type="button" class="sv-comando" data-sv-comando="' + chave + '"' + (ocupado && chave !== "assistente" ? " disabled" : "") + ">" +
    ic(icone, 16) + rotulo + "</button>";
  return '<section class="fin-cartao sv-historico"><div class="fin-cartao-cabeca"><span><span class="sv-faisca">' + ic("auto_awesome", 16) +
    "</span>Resumo da IA</span><small>histórico do serviço · " + plural(eventos.length, "evento") + "</small></div>" +
    '<div class="sv-tempo" id="sv-tempo">' + (linhas || '<p class="nota">Nada aconteceu ainda.</p>') + "</div>" +
    '<div class="sv-conversa"><div class="sv-comandos">' +
    comando("resumo", "auto_awesome", s.resumo ? "Atualizar o resumo" : "Fazer um resumo") +
    comando("falta", "checklist", "O que falta?") +
    comando("assistente", "forum", "Perguntar no Assistente") +
    (s.cadastro_id ? comando("cobrar", "payments", "Cobrar") : "") + "</div>" +
    '<form class="sv-caixa" data-sv-conversa="1"><input type="text" data-sv-pergunta="1" placeholder="Pergunte algo sobre este serviço…"' + (ocupado ? " disabled" : "") + ">" +
    '<button class="enviar" type="submit" title="Enviar" aria-label="Enviar"' + (ocupado ? " disabled" : "") + ">" + ic("arrow_upward", 18) + "</button></form></div></section>";
}

/* Os arquivos da pasta sao apontadores para o Acervo: a ficha de cada um
   (tipo, paginas, analise) vem de la, pelo sha1. */
function arquivoDoAcervo(a) {
  const doc = (sv.acervo || []).find((d) => d.sha1 === a.sha1);
  return doc ? Object.assign({}, doc, { sha1: a.sha1, ligado_em: a.criado_em, nome: doc.nome || a.nome }) : Object.assign({ existe: false, ligado_em: a.criado_em }, a);
}

/* Três à vista e "Ver mais" com o resto, como as conversas recentes do
   Assistente. */
const ARQUIVOS_A_VISTA = 3;

function cartaoDosArquivos(s) {
  const todos = s.arquivos.map(arquivoDoAcervo);
  const mostrar = sv.arquivosAbertos ? todos : todos.slice(0, ARQUIVOS_A_VISTA);
  const linhas = mostrar.map((a) => {
    const sub = [a.tipo_rotulo, a.paginas ? plural(a.paginas, "página") : "", a.analise ? "analisado" : "", a.existe === false ? "não está mais no Acervo" : ""]
      .filter(Boolean).join(" · ");
    return '<div class="tabela-linha colunas-sv-arquivos" data-sv-arquivo="' + esc(a.sha1) + '">' + glifo(a.nome) +
      '<div class="duas-linhas"><b>' + esc(a.nome) + "</b><small>" + esc(sub || "no Acervo") + "</small></div>" +
      '<span class="sv-data">' + esc(a.modificado || quandoCurtoSv(a.ligado_em)) + "</span>" +
      '<button class="mais-linha" data-sv-arquivo-mais="' + esc(a.sha1) + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");
  const verMais = todos.length > ARQUIVOS_A_VISTA
    ? '<div class="sv-arquivos-pe"><button class="ver-mais" data-sv-arquivos-mais="1">' +
      (sv.arquivosAbertos ? "Ver menos" + ic("expand_less", 16) : "Ver mais · " + (todos.length - ARQUIVOS_A_VISTA) + ic("chevron_right", 16)) + "</button></div>"
    : "";
  // "2 documentos · 7 páginas": a conta que diz o tamanho da pasta. O nome
  // da pasta do disco era ruído de caminho, não informação.
  const paginas = todos.reduce((soma, a) => soma + (Number(a.paginas) || 0), 0);
  const conta = todos.length ? plural(todos.length, "documento") + (paginas ? " · " + plural(paginas, "página") : "") : "nenhum documento";
  return '<div class="tabela-cartao sv-arquivos" id="sv-arquivos"><div class="tabela-barra"><b>Arquivos</b><span class="nota-barra">' + esc(conta) + "</span>" +
    '<div class="direita"><button data-sv-ligar="1">' + ic("add", 16) + "Adicionar</button></div></div>" +
    '<div class="tabela-corpo">' + (linhas || '<p class="nota">Nenhum arquivo ligado. Adicionar traz um documento do Acervo para esta pasta — o arquivo continua onde está.</p>') + "</div>" +
    verMais + "</div>";
}

/* Abrir e recolher a lista andam, como o "Ver mais" do Assistente. */
function alternarArquivosDoServico() {
  const velho = document.getElementById("sv-arquivos");
  if (!velho) return;
  const corpoVelho = velho.querySelector(".tabela-corpo");
  const antes = corpoVelho.offsetHeight;
  sv.arquivosAbertos = !sv.arquivosAbertos;
  velho.outerHTML = cartaoDosArquivos(sv.aberto);
  ligarServicos();
  const corpo = document.querySelector("#sv-arquivos .tabela-corpo");
  if (!corpo || !animacoesLigadas()) return;
  const depois = corpo.offsetHeight;
  corpo.style.overflow = "hidden";
  corpo.animate([{ height: antes + "px" }, { height: depois + "px" }], { duration: 420, easing: CURVA_ENTRA })
    .onfinish = () => { corpo.style.overflow = ""; };
  if (sv.arquivosAbertos) {
    corpo.querySelectorAll(".tabela-linha").forEach((linha, i) => {
      if (i < ARQUIVOS_A_VISTA || i > 14) return;
      linha.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }],
        { duration: 360, delay: 60 + (i - ARQUIVOS_A_VISTA) * 26, easing: CURVA_ENTRA, fill: "backwards" });
    });
  }
}

/* ---------------------------------------------------------- o painel */

function painelDoTrabalho() {
  const alca = '<button class="alca-painel" data-sv-alca="1" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(sv.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  const s = sv.aberto;
  return '<aside class="acervo-painel sv-painel">' + alca + '<div class="rolagem">' +
    blocoDaEquipe(s) + blocoDasEtapas(s) + blocoDosPrazos(s) + blocoDasAnotacoes(s) + "</div></aside>";
}

function papelDaPessoa(p, i) {
  const tipo = p.tipo === "socio" ? "sócio" : (p.tipo === "colaborador" ? "colaborador" : p.tipo);
  return (i === 0 ? "responsável · " : "") + (p.observacao ? p.observacao : tipo);
}

function blocoDaEquipe(s) {
  const linhas = s.equipe.map((p, i) => '<div class="sv-pessoa"><span class="cad-avatar">' + esc(iniciaisDoRemetente(p.nome)) +
    '</span><div class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" + esc(papelDaPessoa(p, i)) + "</small></div>" +
    (i === 0 ? '<span class="cad-pill">responsável</span>' : "") +
    '<button class="mais-linha" data-sv-pessoa-tirar="' + p.id + '" title="Tirar da equipe">' + ic("close", 16) + "</button></div>").join("");
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca">Equipe<button class="em-ligacao forte" data-sv-pessoa="1">+ pessoa</button></div>' +
    (linhas || '<p class="nota">Ninguém ainda. A primeira pessoa é a responsável.</p>') + "</div>";
}

function blocoDasEtapas(s) {
  const total = s.etapas.length;
  const linhas = s.etapas.map((e, i) => {
    const classe = "sv-etapa" + (e.feita ? " feita" : "");
    return '<div class="' + classe + '"><button class="sv-marca" data-sv-etapa="' + i + '" title="' + (e.feita ? "Reabrir a etapa" : "Concluir a etapa") + '">' +
      ic(e.feita ? "check_circle" : "radio_button_unchecked", 20) + "</button>" +
      '<div class="duas-linhas"><b>' + esc(e.titulo) + "</b>" + subDaEtapa(e) + "</div>" +
      '<button class="mais-linha" data-sv-etapa-tirar="' + i + '" title="Remover a etapa">' + ic("close", 16) + "</button></div>";
  }).join("");
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca">Status para conclusão<span class="contagem">' +
    (total ? s.progresso + "% · " + s.etapas_feitas + " de " + total : "sem etapas") + "</span></div>" +
    (total ? '<div class="barra-fina"><i style="width:' + s.progresso + '%"></i></div>' : "") +
    (linhas || '<p class="nota">Divida o serviço em etapas: o andamento da pasta é a conta delas.</p>') +
    '<form class="sv-nova-etapa" data-sv-nova-etapa="1"><input type="text" placeholder="Nova etapa…" data-sv-etapa-titulo="1">' +
    '<input type="hidden" data-sv-etapa-quando="1">' +
    '<button type="button" class="sv-escolher-data" data-sv-etapa-data="1" title="Até quando">' + ic("event", 16) + '<span class="sv-data-rotulo">prazo</span></button>' +
    '<button class="primario" type="submit" title="Adicionar" aria-label="Adicionar etapa">' + ic("add", 16) + "</button></form></div>";
}

/* A linha de baixo da etapa. Prazo que já passou, com a etapa aberta, sai
   em vinho e escrito: "atrasado". */
function subDaEtapa(e) {
  const atrasada = !e.feita && e.quando && diasAte(e.quando) < 0;
  const classe = atrasada ? "sv-atrasada" : "";
  const texto = e.feita
    ? "concluído · " + quandoCurtoSv(e.feita_em) + (e.por ? " · " + e.por : "")
    : (e.quando ? "até " + dataCurta(e.quando) + (atrasada ? " · atrasado" : "") : "a fazer");
  return '<small class="' + classe + '">' + esc(texto) + "</small>";
}

function quandoDoPrazoSv(p) {
  const dias = diasAte(p.quando);
  const hora = p.hora ? " " + p.hora : "";
  if (dias === 0) return "hoje" + hora;
  if (dias === 1) return "amanhã" + hora;
  return dataCurta(p.quando) + hora;
}

function blocoDosPrazos(s) {
  const linhas = s.prazos.map((p) => {
    const classe = "sv-prazo-data" + (diasAte(p.quando) <= 0 ? " hoje" : "");
    return '<div class="sv-prazo"><span class="' + classe + '">' + esc(quandoDoPrazoSv(p)) + '</span><div class="duas-linhas"><b>' + esc(p.titulo) +
      "</b><small>" + esc(p.detalhe) + "</small></div></div>";
  }).join("");
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca">Prazos e agendamentos<button class="em-ligacao forte" data-sv-agendar="1">+ agendar</button></div>' +
    (linhas || '<p class="nota">' + (s.cadastro_id ? "Nada agendado para este cliente." : "Ligue um cliente à pasta para ver os prazos e os compromissos dele aqui.") + "</p>") + "</div>";
}

function blocoDasAnotacoes(s) {
  const linhas = s.anotacoes.slice(0, 4).map((a) => '<div class="sv-nota"><div class="sv-nota-cabeca"><span class="cad-avatar">' +
    esc(iniciaisDoRemetente(a.quem)) + "</span><b>" + esc(a.quem) + "</b><small>" + esc(quandoCurtoSv(a.quando)) + "</small></div><p>" + esc(a.texto) + "</p></div>").join("");
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca">Anotações<span class="contagem">' + s.anotacoes.length + "</span></div>" + linhas +
    '<textarea class="sv-nova-nota" rows="2" placeholder="Nova anotação… (Enter guarda)" data-sv-nota="1"></textarea></div>';
}

/* ----------------------------------------------- o que se faz na pasta */

async function conversarSobreServico(pergunta) {
  pergunta = String(pergunta || "").trim();
  if (!pergunta || sv.conversando || !sv.aberto) return;
  const id = sv.aberto.id;
  sv.conversando = { pergunta: pergunta, desde: Date.now() };
  desenharServicos();
  try {
    const r = await fetch("/api/servicos/" + id + "/conversar", { method: "POST", headers: SV_JSON, body: JSON.stringify({ pergunta: pergunta }) });
    if (!r.ok) throw new Error(await erroDe(r));
    const s = await r.json();
    if (sv.aberto && sv.aberto.id === id) sv.aberto = s;
  } catch (err) {
    avisoCert("não consegui responder agora: " + String((err && err.message) || err));
  } finally {
    sv.conversando = null;
    if (sv.visao === "trabalho" && sv.aberto && sv.aberto.id === id) desenharServicos();
  }
}

/* O tempo do que está pensando, a cada meio segundo. */
setInterval(() => {
  document.querySelectorAll("[data-sv-pensando]").forEach((el) => {
    const s = Math.round((Date.now() - Number(el.dataset.svPensando)) / 1000);
    const base = el.dataset.base || el.textContent.replace(/ · \d+ s$/, "");
    el.dataset.base = base;
    el.textContent = base + " · " + s + " s";
  });
}, 500);

/* A equipe, num pop-up: marcar quem já está em Cadastros, ou cadastrar
   alguém novo ali mesmo. A ordem de quem foi marcado é a da equipe — a
   primeira pessoa é a responsável. */
async function dialogoDaEquipe() {
  const s = sv.aberto;
  if (!s) return;
  const pessoas = sv.clientes.filter((c) => c.tipo === "colaborador" || c.tipo === "socio");
  const equipe = s.equipe.map((p) => p.id);
  const linha = (p) => {
    const classe = "sv-d-pessoa" + (equipe.includes(p.id) ? " on" : "");
    return '<button type="button" class="' + classe + '" data-sv-d-pessoa="' + p.id + '"><span class="sv-d-marca">' + ic("check", 12) + "</span>" +
      '<span class="cad-avatar">' + esc(iniciaisDoRemetente(p.nome)) + '</span><span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" +
      esc(p.observacao || (p.tipo === "socio" ? "sócio" : "colaborador")) + "</small></span></button>";
  };
  const lista = pessoas.length
    ? '<div class="sv-d-pessoas">' + pessoas.map(linha).join("") + "</div>"
    : '<p class="dialogo-dica">Ninguém da equipe em Cadastros ainda — cadastre abaixo.</p>';
  const html = '<div class="dialogo-campo"><label>Quem cuida deste serviço</label>' + lista +
    '<input type="hidden" id="sv-d-ids" data-dialogo-chave="equipe" value="' + equipe.join(",") + '"></div>' +
    '<div class="sv-d-nova"><span class="rotulo">Cadastrar nova pessoa</span>' +
    '<div class="dialogo-duas"><div class="dialogo-campo"><label for="sv-d-nome">Nome</label><div class="dialogo-caixa">' + ic("person_add", 18) +
    '<input id="sv-d-nome" data-dialogo-chave="novo_nome" placeholder="Nome completo" autocomplete="off"></div></div>' +
    '<div class="dialogo-campo"><label for="sv-d-tipo">Vínculo</label><div class="dialogo-caixa"><select id="sv-d-tipo" data-dialogo-chave="novo_tipo">' +
    '<option value="colaborador">Colaborador</option><option value="socio">Sócio</option></select></div></div></div>' +
    '<div class="dialogo-campo"><label for="sv-d-funcao">Função</label><div class="dialogo-caixa">' +
    '<input id="sv-d-funcao" data-dialogo-chave="novo_funcao" placeholder="Advogada, estagiário, perito…" autocomplete="off"></div></div>' +
    '<p class="dialogo-dica">Quem for cadastrado aqui entra em Cadastros e já na equipe.</p></div>';

  setTimeout(() => {
    const ids = document.getElementById("sv-d-ids");
    document.querySelectorAll("[data-sv-d-pessoa]").forEach((b) => {
      b.onclick = () => {
        const id = Number(b.dataset.svDPessoa);
        const atuais = ids.value ? ids.value.split(",").map(Number) : [];
        const novos = atuais.includes(id) ? atuais.filter((x) => x !== id) : atuais.concat([id]);
        ids.value = novos.join(",");
        b.classList.toggle("on", novos.includes(id));
      };
    });
  }, 0);

  const r = await dialogo({
    titulo: "Equipe do serviço", contexto: "Serviços › " + s.nome, classe: "dialogo-servico", larga: true,
    depois: html, confirmar: "Guardar equipe",
  });
  if (!r || !r.ok) return;
  const v = r.valores || {};
  const ids = v.equipe ? v.equipe.split(",").map(Number) : [];
  if (v.novo_nome) {
    const criado = await fetch("/api/cadastros", { method: "POST", headers: SV_JSON, body: JSON.stringify({
      id: null, dados: { nome: v.novo_nome, tipo: v.novo_tipo || "colaborador", observacao: v.novo_funcao || "" } }) });
    if (!criado.ok) { avisoCert(await erroDe(criado)); return; }
    const ficha = await criado.json();
    sv.clientes.push({ id: ficha.id, nome: ficha.nome, tipo: ficha.tipo, observacao: ficha.observacao || "" });
    ids.push(ficha.id);
  }
  mudarEquipeDoServico(ids);
}

function dataPorExtenso(iso) {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

/* O prazo da etapa, pelo calendário: cinco anos para cada lado (a mesma
   regra do servidor). Data que já passou vale — a etapa registrada depois do
   fato é comum —, mas o calendário a mostra em vinho e o botão diz
   "atrasado". */
function escolherPrazoDaEtapa(botao) {
  const form = botao.closest("form");
  const campo = form.querySelector("[data-sv-etapa-quando]");
  const hoje = hojeIso();
  calendarioPopover(botao, {
    valor: campo.value, min: somarAnosIso(hoje, -5), max: somarAnosIso(hoje, 5), limpar: true, passado: true,
    marcados: sv.aberto.etapas.map((e) => e.quando).filter(Boolean),
    aoEscolher: (iso) => {
      const atrasada = Boolean(iso) && iso < hoje;
      campo.value = iso;
      botao.querySelector(".sv-data-rotulo").textContent = iso ? dataCurta(iso) + (atrasada ? " · atrasado" : "") : "prazo";
      botao.classList.toggle("com-data", Boolean(iso));
      botao.classList.toggle("atrasado", atrasada);
      botao.title = iso ? "Até " + dataPorExtenso(iso) + (atrasada ? " — já passou: a etapa entra atrasada" : "") : "Até quando";
    },
  });
}

/* Agendar pela pasta: o dia no calendário (nada no passado; os dias que já
   têm algo do cliente vêm marcados), depois o que é e a hora. */
function agendarNoServico(botao) {
  const s = sv.aberto;
  const hoje = hojeIso();
  calendarioPopover(botao, {
    min: hoje, max: somarAnosIso(hoje, 5), marcados: s.prazos.map((p) => p.quando),
    aoEscolher: async (iso) => {
      if (!iso) return;
      const [a, m, d] = iso.split("-").map(Number);
      const semana = new Date(a, m - 1, d).getDay();
      const avisos = [];
      if (semana === 0 || semana === 6) avisos.push("Cai num fim de semana.");
      if (s.prazos.some((p) => p.quando === iso)) avisos.push("Já há algo do cliente neste dia.");
      if (!s.cadastro_id) avisos.push("Sem cliente ligado à pasta, o compromisso vai para a Agenda mas não aparece aqui.");
      const html = '<div class="dialogo-duas"><div class="dialogo-campo"><label for="sv-a-hora">Hora</label><div class="dialogo-caixa">' + ic("schedule", 18) +
        '<input id="sv-a-hora" type="time" data-dialogo-chave="hora" value="09:00"></div></div>' +
        '<div class="dialogo-campo"><label for="sv-a-tipo">Tipo</label><div class="dialogo-caixa"><select id="sv-a-tipo" data-dialogo-chave="tipo">' +
        '<option value="compromisso">Compromisso</option><option value="prazo_interno">Prazo interno</option></select></div></div></div>' +
        (avisos.length ? '<p class="dialogo-dica">' + esc(avisos.join(" ")) + "</p>" : "");
      const r = await dialogo({
        titulo: "Agendar", contexto: maiuscula(dataPorExtenso(iso)), classe: "dialogo-servico",
        campo: { rotulo: "O que é", valor: s.nome, icone: "event", max: 120 },
        depois: html, confirmar: "Agendar",
      });
      if (!r || !r.ok) return;
      const v = r.valores || {};
      const resposta = await fetch("/api/agenda", { method: "POST", headers: SV_JSON, body: JSON.stringify({
        id: null, dados: { titulo: r.valor, tipo: v.tipo || "compromisso", data: iso, hora: v.hora || "09:00", cadastro_id: s.cadastro_id || null } }) });
      if (!resposta.ok) { avisoCert(await erroDe(resposta)); return; }
      avisoCert("agendado para " + dataPorExtenso(iso) + (v.hora ? " às " + v.hora : ""), { tom: "ok" });
      recarregarServico();
    },
  });
}

/* ------------------------------------------------------ o formulario */

/* NOVO SERVIÇO E EDITAR, NO POP-UP DO SISTEMA. Antes era uma coluna lateral
   que empurrava as pastas; agora é o mesmo diálogo da conversa (Novo grupo,
   Renomear): nome, cliente, status, o que está sendo feito e a equipe. */
async function dialogoDoServico(s) {
  const clientes = sv.clientes.filter((c) => c.tipo === "cliente");
  const pessoas = sv.clientes.filter((c) => c.tipo === "colaborador" || c.tipo === "socio");
  const equipe = s ? s.equipe.map((p) => p.id) : [];
  const status = s ? s.status : "andamento";
  const opcoesCliente = '<option value="">sem cliente</option>' + clientes.map((c) =>
    '<option value="' + c.id + '"' + (s && c.id === s.cadastro_id ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("");
  const opcoesStatus = sv.status.map((x) =>
    '<option value="' + x.valor + '"' + (x.valor === status ? " selected" : "") + ">" + esc(x.rotulo) + "</option>").join("");
  const chips = pessoas.length
    ? pessoas.map((p) => {
      const classe = equipe.includes(p.id) ? "on" : "";
      return '<button type="button" class="' + classe + '" data-sv-chip="' + p.id + '">' + esc(p.nome) + "</button>";
    }).join("")
    : '<span class="ag-vazio-chip">ninguém na equipe em Cadastros ainda</span>';
  const html =
    '<div class="dialogo-duas">' +
    '<div class="dialogo-campo"><label for="sv-d-cliente">Cliente</label><div class="dialogo-caixa">' +
    '<select id="sv-d-cliente" data-dialogo-chave="cadastro_id">' + opcoesCliente + "</select></div></div>" +
    '<div class="dialogo-campo"><label for="sv-d-status">Status</label><div class="dialogo-caixa">' +
    '<select id="sv-d-status" data-dialogo-chave="status">' + opcoesStatus + "</select></div></div></div>" +
    '<div class="dialogo-campo"><label for="sv-d-descricao">O que está sendo feito</label><div class="dialogo-caixa texto-longo">' +
    '<textarea id="sv-d-descricao" rows="3" data-dialogo-chave="descricao" placeholder="Aviso de não renovação, renegociação do contrato e aditivo com novo prazo.">' +
    esc(s ? s.descricao || "" : "") + "</textarea></div></div>" +
    '<div class="dialogo-campo"><label>Equipe — a primeira pessoa é a responsável</label>' +
    '<div class="ag-chips" id="sv-d-equipe">' + chips + "</div>" +
    '<input type="hidden" id="sv-d-equipe-ids" data-dialogo-chave="equipe" value="' + equipe.join(",") + '"></div>';

  // Os botões da equipe entram depois que o diálogo existe.
  setTimeout(() => {
    const lugar = document.getElementById("sv-d-equipe");
    const ids = document.getElementById("sv-d-equipe-ids");
    if (!lugar || !ids) return;
    lugar.querySelectorAll("[data-sv-chip]").forEach((b) => {
      b.onclick = () => {
        const id = Number(b.dataset.svChip);
        const atuais = ids.value ? ids.value.split(",").map(Number) : [];
        const novos = atuais.includes(id) ? atuais.filter((x) => x !== id) : atuais.concat([id]);
        ids.value = novos.join(",");
        b.classList.toggle("on", novos.includes(id));
      };
    });
  }, 0);

  const r = await dialogo({
    titulo: s ? "Editar serviço" : "Novo serviço",
    contexto: s ? "Serviços › " + s.nome : "Serviços",
    campo: { rotulo: "Nome", valor: s ? s.nome : "", placeholder: "Renovação Fornecedor A", icone: "folder", max: 80 },
    classe: "dialogo-servico",
    larga: true,
    depois: html + '<p class="dialogo-dica">' + (s ? "A trilha da pasta guarda a mudança." : "Arquivos, prazos e anotações entram depois, dentro da pasta.") + "</p>",
    confirmar: s ? "Guardar" : "Abrir serviço",
  });
  if (!r || !r.ok) return;
  const v = r.valores || {};
  const dados = {
    nome: r.valor, cadastro_id: Number(v.cadastro_id) || null, status: v.status || "andamento",
    descricao: v.descricao || "", equipe: v.equipe ? v.equipe.split(",").map(Number) : [],
  };
  const resposta = await fetch("/api/servicos", { method: "POST", headers: SV_JSON, body: JSON.stringify({ id: s ? s.id : null, dados: dados }) });
  if (!resposta.ok) { avisoCert(await erroDe(resposta)); return; }
  const salvo = await resposta.json();
  if (s) {
    avisoCert("serviço guardado");
    if (sv.visao === "trabalho" && sv.aberto && sv.aberto.id === salvo.id) { sv.aberto = salvo; return mostrarServicos("trabalho"); }
    return mostrarServicos("pastas");
  }
  avisoCert("serviço aberto: " + salvo.nome);
  abrirServico(salvo.id);
}

/* O nome da pasta, escrito no próprio título. O resto da ficha vai junto
   como está: o servidor grava a ficha inteira. */
async function renomearServico(s, novo) {
  const r = await fetch("/api/servicos", {
    method: "POST", headers: SV_JSON,
    body: JSON.stringify({ id: s.id, dados: {
      nome: novo, cadastro_id: s.cadastro_id || null, descricao: s.descricao || "", status: s.status,
      equipe: (s.equipe || []).map((p) => p.id),
    } }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  const salvo = await r.json();
  if (sv.aberto && sv.aberto.id === s.id) Object.assign(sv.aberto, { nome: salvo.nome });
  return true;
}

/* ------------------------------------------------------------ ligar */

function ligarServicos() {
  const clique = (sel, fn) => document.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });
  const busca = $("sv-busca");
  if (busca) {
    let t;
    busca.oninput = () => { clearTimeout(t); const v = busca.value; t = setTimeout(() => { sv.termo = v.trim(); mostrarServicos("pastas"); }, 280); };
  }
  clique("[data-sv-filtro]", (b) => { sv.filtro = b.dataset.svFiltro; mostrarServicos("pastas"); });
  clique("[data-sv-voltar]", () => { sv.visao = "pastas"; mostrarServicos("pastas"); });
  clique("[data-sv-novo]", () => dialogoDoServico(null));
  clique("[data-sv-abrir]", (b) => abrirServico(Number(b.dataset.svAbrir)));
  ligarSelecao(document.querySelector("#sv-tela .sv-grade"), {
    linhas: ".sv-pasta[data-sel]", escolhidos: sv.escolhidos, aoMudar: desenharServicos, apagar: (ids) => apagarServicosEmLote(ids),
  });
  clique("[data-sv-sel-limpar]", () => { sv.escolhidos.clear(); desenharServicos(); });
  clique("[data-sv-sel-apagar]", () => apagarServicosEmLote([...sv.escolhidos]));
  clique("[data-sv-sel-concluir]", () => concluirServicosEmLote([...sv.escolhidos]));
  clique("[data-sv-mais]", (b) => menuDoServico(b, sv.lista.find((x) => x.id === Number(b.dataset.svMais))));
  clique("[data-sv-editar]", () => dialogoDoServico(sv.aberto));
  clique("[data-sv-comando]", (b) => {
    const c = b.dataset.svComando;
    if (c === "resumo") pedirResumoDoServico();
    else if (c === "falta") conversarSobreServico("O que falta para concluir este serviço?");
    else if (c === "assistente") perguntarSobreServico(sv.aberto);
    else if (c === "cobrar") cobrarDoServico(sv.aberto);
  });
  const conversa = document.querySelector("[data-sv-conversa]");
  if (conversa) conversa.onsubmit = (e) => { e.preventDefault(); conversarSobreServico(conversa.querySelector("[data-sv-pergunta]").value); };
  clique("[data-sv-arquivos-mais]", () => alternarArquivosDoServico());
  clique("[data-sv-etapa-data]", (b) => escolherPrazoDaEtapa(b));
  const tempo = document.getElementById("sv-tempo");
  if (tempo) tempo.scrollTop = tempo.scrollHeight;
  clique("[data-sv-status]", (b) => mudarStatusDoServico(sv.aberto.id, b.dataset.svStatus));
  clique("[data-sv-etapa]", (b) => alternarEtapa(Number(b.dataset.svEtapa)));
  clique("[data-sv-etapa-tirar]", (b) => tirarEtapa(Number(b.dataset.svEtapaTirar)));
  const nova = document.querySelector("[data-sv-nova-etapa]");
  if (nova) nova.onsubmit = (e) => { e.preventDefault(); adicionarEtapa(nova); };
  clique("[data-sv-ligar]", () => adicionarArquivosAoServico());
  clique("[data-sv-arquivo]", (b) => abrirArquivoDoServico(b.dataset.svArquivo));
  clique("[data-sv-arquivo-mais]", (b) => menuDoArquivoDoServico(b, b.dataset.svArquivoMais));
  clique("[data-sv-pessoa]", () => dialogoDaEquipe());
  clique("[data-sv-pessoa-tirar]", (b) => mudarEquipeDoServico(sv.aberto.equipe.map((p) => p.id).filter((id) => id !== Number(b.dataset.svPessoaTirar))));
  clique("[data-sv-agendar]", (b) => agendarNoServico(b));
  const nota = document.querySelector("[data-sv-nota]");
  if (nota) nota.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); anotarNoServico(nota.value); } };
  clique("[data-sv-alca]", () => { sv.largo = !sv.largo; desenharServicos(); });
}

/* ------------------------------------------------------------ acoes */

function menuDoServico(botao, s) {
  if (!s) return;
  menuNaLinha(botao, [
    { rotulo: "Abrir a pasta", acao: () => abrirServico(s.id) },
    { rotulo: "Editar", acao: () => dialogoDoServico(s) },
    { rotulo: "Marcar", sub: sv.status.filter((x) => x.valor !== s.status)
      .map((x) => ({ rotulo: x.rotulo, acao: () => mudarStatusDoServico(s.id, x.valor) })) },
    "-",
    { rotulo: "Apagar", perigo: true, acao: () => apagarServico(s) },
  ]);
}

async function apagarServico(s) {
  if (!(await confirmar({ titulo: "Apagar este serviço?", contexto: "Serviços › " + s.nome, texto: "A trilha e as anotações vão junto. Os arquivos ficam no Acervo; os prazos, na Agenda. " + LIXEIRA_TEXTO, confirmar: "Apagar", perigo: true }))) return;
  const r = await fetch("/api/servicos/" + s.id, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  if (sv.aberto && sv.aberto.id === s.id) sv.aberto = null;
  mostrarServicos("pastas");
  avisarLixeira(r, () => mostrarServicos("pastas"));
}

function apagarServicosEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/servicos/" + id, {
    rotulo: "serviço", contexto: "Serviços", texto: "A trilha e as anotações vão junto. Os arquivos ficam no Acervo; os prazos, na Agenda.",
    depois: () => { sv.escolhidos.clear(); if (sv.aberto && ids.includes(String(sv.aberto.id))) sv.aberto = null; mostrarServicos("pastas"); },
  });
}

async function concluirServicosEmLote(ids) {
  let feitos = 0;
  for (const id of ids) {
    const r = await fetch("/api/servicos/" + id + "/status", { method: "POST", headers: SV_JSON, body: JSON.stringify({ status: "concluido" }) });
    if (r.ok) feitos += 1;
  }
  sv.escolhidos.clear();
  avisoCert(plural(feitos, "serviço") + (feitos === 1 ? " concluído" : " concluídos"), { tom: "ok" });
  mostrarServicos("pastas");
}

async function mudarStatusDoServico(id, status) {
  const r = await fetch("/api/servicos/" + id + "/status", { method: "POST", headers: SV_JSON, body: JSON.stringify({ status: status }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const s = await r.json();
  avisoCert(s.nome + ": " + s.status_rotulo.toLowerCase());
  if (sv.visao === "trabalho" && sv.aberto && sv.aberto.id === id) { sv.aberto = s; return mostrarServicos("trabalho"); }
  mostrarServicos("pastas");
}

async function alternarEtapa(i) {
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/etapas/" + i, { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  recarregarServico();
}

async function tirarEtapa(i) {
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/etapas/" + i, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  recarregarServico();
}

async function adicionarEtapa(form) {
  const titulo = form.querySelector("[data-sv-etapa-titulo]").value.trim();
  const quando = form.querySelector("[data-sv-etapa-quando]").value;
  if (!titulo) return;
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/etapas", { method: "POST", headers: SV_JSON, body: JSON.stringify({ titulo: titulo, quando: quando }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  await recarregarServico();
  const campo = document.querySelector("[data-sv-etapa-titulo]");
  if (campo) campo.focus();
}

async function anotarNoServico(texto) {
  if (!texto.trim()) return;
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/anotacoes", { method: "POST", headers: SV_JSON, body: JSON.stringify({ texto: texto.trim() }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  recarregarServico();
}

async function mudarEquipeDoServico(ids) {
  const s = sv.aberto;
  const dados = { nome: s.nome, cadastro_id: s.cadastro_id, descricao: s.descricao, status: s.status, equipe: ids };
  const r = await fetch("/api/servicos", { method: "POST", headers: SV_JSON, body: JSON.stringify({ id: s.id, dados: dados }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  sv.aberto = await r.json();
  desenharServicos();
}

/* Adicionar abre o mesmo pop-up do anexar da conversa: os documentos do
   Acervo, ou as pastas deste computador. O que vem do computador é copiado
   para o Acervo e lido; depois, tudo é ligado à pasta pelo sha1. */
function adicionarArquivosAoServico() {
  const s = sv.aberto;
  if (!s) return;
  abrirAnexar({
    titulo: "Adicionar à pasta", contexto: "Serviços › " + s.nome, verbo: "Adicionar",
    aoAnexar: async (nomes) => {
      if (!nomes.length) return;
      try { sv.acervo = (await (await fetch("/api/biblioteca")).json()).documentos || []; } catch (err) { /* segue com o que tinha */ }
      let ligados = 0;
      for (const nome of nomes) {
        const doc = (sv.acervo || []).find((d) => d.nome === nome);
        if (!doc) continue;
        const r = await fetch("/api/servicos/" + s.id + "/vincular", { method: "POST", headers: SV_JSON, body: JSON.stringify({ sha1: doc.sha1, nome: doc.nome }) });
        if (r.ok) ligados += 1;
      }
      avisoCert(ligados ? plural(ligados, "documento") + (ligados === 1 ? " adicionado à pasta" : " adicionados à pasta") : "nenhum documento foi adicionado", { tom: ligados ? "ok" : "erro" });
      recarregarServico();
    },
  });
}

async function desligarDocumentoDoServico(sha1) {
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/vinculos/" + sha1, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  recarregarServico();
}

function abrirArquivoDoServico(sha1) {
  const a = arquivoDoAcervo({ sha1: sha1 });
  if (a.existe === false || !a.caminho) { avisoCert("esse arquivo não está mais no Acervo — desligue-o da pasta ou traga-o de volta"); return; }
  abrirDoAcervo(a);
}

function menuDoArquivoDoServico(botao, sha1) {
  const a = arquivoDoAcervo(sv.aberto.arquivos.find((x) => x.sha1 === sha1) || { sha1: sha1, nome: "" });
  menuNaLinha(botao, [
    { rotulo: "Abrir", icone: "open_in_new", acao: () => abrirArquivoDoServico(sha1) },
    { rotulo: "Ver no Acervo", icone: "inventory_2", acao: () => verNoAcervo(a.nome) },
    "-",
    { rotulo: "Desligar desta pasta", icone: "link", perigo: true, acao: () => desligarDocumentoDoServico(sha1) },
  ]);
}

async function pedirResumoDoServico() {
  if (sv.pedindo) return;
  sv.pedindo = true;
  sv.pedindoDesde = Date.now();
  desenharServicos();
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/resumo", { method: "POST" });
  sv.pedindo = false;
  if (!r.ok) {
    avisoCert("sem resumo agora: " + (await erroDe(r)));
    desenharServicos();
    return;
  }
  sv.aberto = await r.json();
  desenharServicos();
}

function perguntarSobreServico(s) {
  if (!s) return;
  $("nova").click();
  marcarDestino("conversa");
  const campo = $("pedido");
  if (!campo) return;
  const arquivos = (s.arquivos || []).slice(0, 5).map((a) => a.nome).join(", ");
  campo.value = "Sobre o serviço “" + s.nome + "”" + (s.cliente_nome ? " (cliente " + s.cliente_nome + ")" : "") +
    (arquivos ? ", com os arquivos " + arquivos : "") + ": ";
  campo.focus();
  campo.setSelectionRange(campo.value.length, campo.value.length);
}

/* Cobrar abre um lancamento a receber ja preenchido no Financeiro. */
function cobrarDoServico(s) {
  if (!s || !s.cadastro_id) return;
  const mes = mesDeHoje();
  fin.visao = "lancamentos";
  fin.aberto = null;
  fin.form = {
    id: null, tipo: "recebimento", descricao: "Honorários — " + s.nome, valor: "", categoria: "honorarios",
    cadastro_id: s.cadastro_id, vencimento: ultimoDiaDoMes(mes), liquidado_em: "",
  };
  mostrarFinanceiro("lancamentos");
}


