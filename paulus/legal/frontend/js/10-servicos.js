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
  aberto: null, aba: "geral", form: null, acervo: null, acervoTermo: "", ligar: false, largo: false,
  pedindo: false, salvando: false, escolhidos: new Set(),
};

async function mostrarServicos(visao) {
  if (visao) sv.visao = visao;
  if (sv.visao === "trabalho" && !sv.aberto) sv.visao = "pastas";
  if (sv.visao === "pastas") { sv.ligar = false; sv.form = sv.form && !sv.form.id ? sv.form : null; }
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
  sv.aba = "geral";
  sv.form = null;
  sv.ligar = false;
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
    const classe = "acervo sv-tela" + (sv.form ? (sv.largo ? " painel-largo" : "") : " sem-painel");
    html = '<div class="' + classe + '" id="sv-tela">' + corpoDasPastas() + (sv.form ? painelDoFormServico() : "") + "</div>";
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
    meta.textContent = (s.cliente_nome ? s.cliente_nome + " · " : "") + s.status_rotulo + " · " + s.progresso + "%";
    $("acoes-tela").innerHTML =
      '<div class="visoes">' + botao("aba", "geral", "Visão geral") + botao("aba", "arquivos", "Arquivos") + botao("aba", "trilha", "Trilha") + "</div>" +
      '<button class="primario com-icone" data-sv-perguntar="1">' + ic("forum", 16) + "Perguntar sobre este</button>" +
      (s.status === "concluido"
        ? '<button class="com-icone" data-sv-status="andamento">' + ic("restart_alt", 16) + "Reabrir serviço</button>"
        : '<button class="com-icone" data-sv-status="concluido">' + ic("task_alt", 16) + "Concluir serviço</button>");
    return;
  }
  nav.innerHTML = "";
  titulo.textContent = "Serviços";
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
    '<div class="sv-pasta-pe"><span class="fin-status">' + esc(s.status_rotulo) + '</span><b class="sv-pct">' + s.progresso + "%</b>" +
    (s.equipe.length ? '<span class="sv-avatares">' + s.equipe.slice(0, 3).map((p) =>
      '<span class="cad-avatar" title="' + esc(p.nome) + '">' + esc(iniciaisDoRemetente(p.nome)) + "</span>").join("") + "</span>" : "") +
    "<span>" + plural(s.arquivos_quantos, "arquivo") + " · " + plural(s.prazos_quantos, "prazo") + "</span>" +
    (proximo ? '<span class="' + classeProximo + '">' + ic("event_upcoming", 16) + esc(proximo.texto) + "</span>" : "") +
    "</div></div>";
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

function corpoDoTrabalho() {
  const s = sv.aberto;
  let miolo;
  if (sv.aba === "arquivos") miolo = cartaoDosArquivos(s, false);
  else if (sv.aba === "trilha") miolo = cartaoDaTrilha(s);
  else miolo = '<div class="sv-trabalho">' + cartaoDoResumo(s) + cartaoDasEtapas(s) + "</div>" + cartaoDosArquivos(s, true);
  return '<div class="acervo-principal">' + miolo + "</div>";
}

function cartaoDoResumo(s) {
  const abertas = s.etapas.filter((e) => !e.feita);
  const meta = s.resumo
    ? "atualizado " + haQuantoSv(s.resumo_em) + " · " + plural(s.arquivos.length, "arquivo") + " na pasta"
    : "ainda sem resumo";
  let corpo;
  if (sv.pedindo) corpo = '<p class="sv-resumo-texto vazio">escrevendo o resumo… o modelo local lê o que está gravado nesta pasta.</p>';
  else if (s.resumo) corpo = '<p class="sv-resumo-texto">' + esc(s.resumo) + "</p>";
  else corpo = '<p class="sv-resumo-texto vazio">O assistente ainda não escreveu sobre este serviço. Ao pedir, ele lê o que está gravado aqui — etapas, prazos, anotações e os nomes dos arquivos — e diz onde o serviço está e o que falta. Ele não inventa data nem valor.</p>';
  return '<div class="fin-cartao sv-resumo"><div class="fin-cartao-cabeca"><span><span class="sv-faisca">' + ic("auto_awesome", 16) + "</span>Resumo da IA</span><small>" + esc(meta) + "</small></div>" +
    '<div class="sv-cartao-corpo">' + corpo +
    (abertas.length ? '<div><span class="rotulo">O que falta</span><ul class="sv-falta">' + abertas.slice(0, 3).map((e) =>
      "<li>" + esc(e.titulo) + (e.quando ? " — até " + dataCurta(e.quando) : "") + "</li>").join("") + "</ul></div>" : "") +
    '<div class="fin-botoes"><button class="primario com-icone" data-sv-perguntar="1">' + ic("forum", 16) + "Perguntar sobre este serviço</button>" +
    '<button class="com-icone" data-sv-resumo="1"' + (sv.pedindo ? " disabled" : "") + ">" + ic("auto_awesome", 16) + (s.resumo ? "Atualizar resumo" : "Pedir resumo") + "</button>" +
    (s.cadastro_id ? '<button class="com-icone" data-sv-cobrar="1">' + ic("payments", 16) + "Cobrar</button>" : "") +
    "</div></div></div>";
}

function cartaoDasEtapas(s) {
  const total = s.etapas.length;
  const meta = total ? s.progresso + "% · " + s.etapas_feitas + " de " + plural(total, "etapa") : "sem etapas ainda";
  const linhas = s.etapas.map((e, i) => {
    const classe = "sv-etapa" + (e.feita ? " feita" : "");
    const sub = e.feita
      ? "concluído · " + quandoCurtoSv(e.feita_em) + (e.por ? " · " + e.por : "")
      : (e.quando ? "até " + dataCurta(e.quando) + (diasAte(e.quando) < 0 ? " · atrasado" : "") : "a fazer");
    return '<div class="' + classe + '"><button class="sv-marca" data-sv-etapa="' + i + '" title="' + (e.feita ? "Reabrir a etapa" : "Concluir a etapa") + '">' +
      ic(e.feita ? "check_circle" : "radio_button_unchecked", 20) + "</button>" +
      '<div class="duas-linhas"><b>' + esc(e.titulo) + "</b><small>" + esc(sub) + "</small></div>" +
      '<button class="mais-linha" data-sv-etapa-tirar="' + i + '" title="Remover a etapa">' + ic("close", 16) + "</button></div>";
  }).join("");
  return '<div class="fin-cartao sv-etapas"><div class="fin-cartao-cabeca">Status para conclusão<small>' + esc(meta) + "</small></div>" +
    '<div class="sv-cartao-corpo">' + (linhas || '<p class="nota">Divida o serviço em etapas: o andamento da pasta é a conta delas.</p>') +
    '<form class="sv-nova-etapa" data-sv-nova-etapa="1"><input type="text" placeholder="Nova etapa…" data-sv-etapa-titulo="1">' +
    '<input type="date" data-sv-etapa-quando="1" title="Até quando"><button class="primario" type="submit" title="Adicionar">' + ic("add", 16) + "</button></form>" +
    "</div></div>";
}

/* Os arquivos da pasta sao apontadores para o Acervo: a ficha de cada um
   (tipo, paginas, analise) vem de la, pelo sha1. */
function arquivoDoAcervo(a) {
  const doc = (sv.acervo || []).find((d) => d.sha1 === a.sha1);
  return doc ? Object.assign({}, doc, { sha1: a.sha1, ligado_em: a.criado_em, nome: doc.nome || a.nome }) : Object.assign({ existe: false, ligado_em: a.criado_em }, a);
}

function pastaDosArquivos(arquivos) {
  const contas = {};
  arquivos.forEach((a) => { if (a.pasta_curta) contas[a.pasta_curta] = (contas[a.pasta_curta] || 0) + 1; });
  const pastas = Object.keys(contas).sort((x, y) => contas[y] - contas[x]);
  return pastas[0] || "";
}

function cartaoDosArquivos(s, resumido) {
  const todos = s.arquivos.map(arquivoDoAcervo);
  const mostrar = resumido ? todos.slice(0, 6) : todos;
  const pasta = pastaDosArquivos(todos);
  const linhas = mostrar.map((a) => {
    const sub = [a.tipo_rotulo, a.paginas ? plural(a.paginas, "página") : "", a.analise ? "analisado" : "", a.existe === false ? "não está mais no Acervo" : ""]
      .filter(Boolean).join(" · ");
    return '<div class="tabela-linha colunas-sv-arquivos" data-sv-arquivo="' + esc(a.sha1) + '">' + glifo(a.nome) +
      '<div class="duas-linhas"><b>' + esc(a.nome) + "</b><small>" + esc(sub || "no Acervo") + "</small></div>" +
      '<span class="sv-data">' + esc(a.modificado || quandoCurtoSv(a.ligado_em)) + "</span>" +
      '<button class="mais-linha" data-sv-arquivo-mais="' + esc(a.sha1) + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");
  return '<div class="tabela-cartao sv-arquivos"><div class="tabela-barra"><b>Arquivos</b><span class="nota-barra">' + todos.length +
    (pasta ? " · pasta " + esc(pasta) : "") + "</span>" +
    '<div class="direita"><button data-sv-ligar="1">' + ic("add", 16) + 'Adicionar</button><button data-sv-acervo="1">' + ic("inventory_2", 16) + "Abrir no Acervo</button></div></div>" +
    '<div class="tabela-corpo">' + (linhas || '<p class="nota">Nenhum arquivo ligado. Adicionar traz um documento do Acervo para esta pasta — o arquivo continua onde está.</p>') + "</div>" +
    (resumido && todos.length > mostrar.length
      ? '<div class="tabela-rodape"><span>' + mostrar.length + " de " + todos.length + '</span><button class="mais" data-sv-aba="arquivos">Todos os arquivos →</button></div>'
      : "") + "</div>";
}

function linhaDaTrilha(e, grande) {
  const classe = "sv-evento" + (grande ? " grande" : "");
  return '<div class="' + classe + '"><b>' + esc(e.texto) + "</b><small>" + esc(e.quem) + " · " + esc(quandoCurtoSv(e.quando)) + "</small></div>";
}

function cartaoDaTrilha(s) {
  return '<div class="tabela-cartao sv-trilha-cartao"><div class="tabela-barra"><b>Trilha do serviço</b><span class="nota-barra">' + plural(s.trilha.length, "evento") +
    ' · aberto ' + esc(quandoCurtoSv(s.criado_em)) + "</span></div>" +
    '<div class="tabela-corpo">' + (s.trilha.map((e) => linhaDaTrilha(e, true)).join("") || '<p class="nota">Nada aconteceu ainda.</p>') + "</div></div>";
}

/* ---------------------------------------------------------- o painel */

function painelDoTrabalho() {
  const alca = '<button class="alca-painel" data-sv-alca="1" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(sv.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  if (sv.form) return painelDoFormServico();
  if (sv.ligar) return painelDeLigar();
  const s = sv.aberto;
  return '<aside class="acervo-painel sv-painel">' + alca + '<div class="rolagem">' +
    blocoDaEquipe(s) + blocoDosPrazos(s) + blocoDasAnotacoes(s) + blocoDaTrilha(s) + "</div></aside>";
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
    (linhas || '<p class="nota">Ninguém ainda. A primeira pessoa é a responsável; a equipe vem de Cadastros.</p>') + "</div>";
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
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca">Prazos e agendamentos<span class="contagem">' + s.prazos.length + "</span></div>" +
    (linhas || '<p class="nota">' + (s.cadastro_id ? "Nada agendado para este cliente." : "Ligue um cliente à pasta para ver os prazos e os compromissos dele aqui.") + "</p>") +
    '<button class="em-ligacao" data-sv-agendar="1">+ agendar</button></div>';
}

function blocoDasAnotacoes(s) {
  const linhas = s.anotacoes.slice(0, 4).map((a) => '<div class="sv-nota"><div class="sv-nota-cabeca"><span class="cad-avatar">' +
    esc(iniciaisDoRemetente(a.quem)) + "</span><b>" + esc(a.quem) + "</b><small>" + esc(quandoCurtoSv(a.quando)) + "</small></div><p>" + esc(a.texto) + "</p></div>").join("");
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca">Anotações<span class="contagem">' + s.anotacoes.length + "</span></div>" + linhas +
    '<textarea class="sv-nova-nota" rows="2" placeholder="Nova anotação… (Enter guarda)" data-sv-nota="1"></textarea></div>';
}

function blocoDaTrilha(s) {
  return '<div class="painel-bloco"><div class="painel-bloco-cabeca">Trilha do serviço<span class="contagem">' + plural(s.trilha.length, "evento") + "</span></div>" +
    '<div class="sv-trilha">' + s.trilha.slice(0, 5).map((e) => linhaDaTrilha(e, false)).join("") + "</div>" +
    (s.trilha.length > 5 ? '<button class="em-ligacao" data-sv-aba="trilha">Ver a trilha completa →</button>' : "") + "</div>";
}

function painelDeLigar() {
  const s = sv.aberto;
  const ja = new Set(s.arquivos.map((a) => a.sha1));
  const termo = sv.acervoTermo.trim().toLowerCase();
  const docs = (sv.acervo || []).filter((d) => !ja.has(d.sha1) &&
    (!termo || (d.nome + " " + (d.pasta_curta || "") + " " + (d.cliente || "")).toLowerCase().includes(termo))).slice(0, 30);
  let lista;
  if (docs.length) {
    lista = docs.map((d) => '<div class="sv-doc"><div class="duas-linhas"><b>' + esc(d.nome) + "</b><small>" +
      esc([d.tipo_rotulo, d.pasta_curta].filter(Boolean).join(" · ") || "no Acervo") + "</small></div>" +
      '<button class="em-ligacao forte" data-sv-ligar-doc="' + esc(d.sha1) + '">Ligar</button></div>').join("");
  } else if (sv.acervo && sv.acervo.length) {
    lista = '<p class="nota">' + (termo ? "Nada com esse nome fora desta pasta." : "Todos os documentos do Acervo já estão nesta pasta.") + "</p>";
  } else {
    lista = '<p class="nota">O Acervo está vazio — coloque documentos nele primeiro.</p>';
  }
  return '<aside class="acervo-painel sv-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><div class="titulo-painel"><h3>Ligar do Acervo</h3><div class="meta">o arquivo continua onde está; a pasta só aponta para ele</div></div>' +
    '<button class="mais-linha" data-sv-ligar-fechar="1" title="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="painel-bloco"><label class="busca-tela sv-busca-acervo">' + ic("search", 18) +
    '<input type="text" placeholder="Buscar no Acervo…" data-sv-acervo-termo="1" value="' + esc(sv.acervoTermo) + '"></label>' + lista + "</div></div></aside>";
}

/* ------------------------------------------------------ o formulario */

function formDoServico(s) {
  return {
    id: s ? s.id : null, nome: s ? s.nome : "", cadastro_id: s ? (s.cadastro_id || null) : null,
    descricao: s ? (s.descricao || "") : "", status: s ? s.status : "andamento",
    equipe: s ? s.equipe.map((p) => p.id) : [],
  };
}

function painelDoFormServico() {
  const f = sv.form;
  const clientes = sv.clientes.filter((c) => c.tipo === "cliente");
  const equipe = sv.clientes.filter((c) => c.tipo === "colaborador" || c.tipo === "socio");
  const opcoes = '<option value="">sem cliente</option>' + clientes.map((c) =>
    '<option value="' + c.id + '"' + (c.id === f.cadastro_id ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("");
  const status = sv.status.map((x) => '<option value="' + x.valor + '"' + (x.valor === f.status ? " selected" : "") + ">" + esc(x.rotulo) + "</option>").join("");
  const chips = equipe.length
    ? equipe.map((p) => { const classe = f.equipe.includes(p.id) ? "on" : ""; return '<button type="button" class="' + classe + '" data-sv-chip="' + p.id + '">' + esc(p.nome) + "</button>"; }).join("")
    : '<span class="ag-vazio-chip">ninguém na equipe em Cadastros ainda</span>';
  return '<aside class="acervo-painel sv-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><div class="titulo-painel"><h3>' + (f.id ? "Editar serviço" : "Novo serviço") + '</h3><div class="meta">' +
    (f.id ? "a trilha guarda a mudança" : "uma pasta de trabalho com nome próprio") + "</div></div></div>" +
    '<div class="ag-form">' +
    '<div class="ag-campo"><label>Nome</label><input type="text" data-sv-campo="nome" value="' + esc(f.nome) + '" placeholder="Renovação Fornecedor A"></div>' +
    '<div class="ag-duas"><div class="ag-campo"><label>Cliente</label><select data-sv-campo="cadastro_id">' + opcoes + "</select></div>" +
    '<div class="ag-campo"><label>Status</label><select data-sv-campo="status">' + status + "</select></div></div>" +
    '<div class="ag-campo"><label>O que está sendo feito</label><textarea rows="3" data-sv-campo="descricao" placeholder="Aviso de não renovação, renegociação do contrato e aditivo com novo prazo.">' + esc(f.descricao) + "</textarea></div>" +
    '<div class="ag-campo"><label>Equipe — a primeira pessoa é a responsável</label><div class="ag-chips">' + chips + "</div></div>" +
    '<div class="ag-form-rodape"><button class="primario" data-sv-salvar="1"' + (sv.salvando ? " disabled" : "") + ">" + (f.id ? "Guardar" : "Abrir serviço") + "</button>" +
    '<button data-sv-cancelar="1">Cancelar</button><p class="ag-explica">Arquivos, prazos e anotações entram depois, dentro da pasta.</p></div>' +
    "</div></div></aside>";
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
  clique("[data-sv-aba]", (b) => { sv.aba = b.dataset.svAba; desenharServicos(); });
  clique("[data-sv-voltar]", () => { sv.visao = "pastas"; sv.form = null; sv.ligar = false; mostrarServicos("pastas"); });
  clique("[data-sv-novo]", () => { sv.form = formDoServico(null); sv.ligar = false; desenharServicos(); const c = document.querySelector('[data-sv-campo="nome"]'); if (c) c.focus(); });
  clique("[data-sv-abrir]", (b) => abrirServico(Number(b.dataset.svAbrir)));
  ligarSelecao(document.querySelector("#sv-tela .sv-grade"), {
    linhas: ".sv-pasta[data-sel]", escolhidos: sv.escolhidos, aoMudar: desenharServicos, apagar: (ids) => apagarServicosEmLote(ids),
  });
  clique("[data-sv-sel-limpar]", () => { sv.escolhidos.clear(); desenharServicos(); });
  clique("[data-sv-sel-apagar]", () => apagarServicosEmLote([...sv.escolhidos]));
  clique("[data-sv-sel-concluir]", () => concluirServicosEmLote([...sv.escolhidos]));
  clique("[data-sv-mais]", (b) => menuDoServico(b, sv.lista.find((x) => x.id === Number(b.dataset.svMais))));
  clique("[data-sv-perguntar]", () => perguntarSobreServico(sv.aberto));
  clique("[data-sv-status]", (b) => mudarStatusDoServico(sv.aberto.id, b.dataset.svStatus));
  clique("[data-sv-resumo]", () => pedirResumoDoServico());
  clique("[data-sv-cobrar]", () => cobrarDoServico(sv.aberto));
  clique("[data-sv-etapa]", (b) => alternarEtapa(Number(b.dataset.svEtapa)));
  clique("[data-sv-etapa-tirar]", (b) => tirarEtapa(Number(b.dataset.svEtapaTirar)));
  const nova = document.querySelector("[data-sv-nova-etapa]");
  if (nova) nova.onsubmit = (e) => { e.preventDefault(); adicionarEtapa(nova); };
  clique("[data-sv-ligar]", () => abrirLigarDoAcervo());
  clique("[data-sv-ligar-fechar]", () => { sv.ligar = false; desenharServicos(); });
  clique("[data-sv-ligar-doc]", (b) => ligarDocumentoAoServico(b.dataset.svLigarDoc));
  const termo = document.querySelector("[data-sv-acervo-termo]");
  if (termo) termo.oninput = () => { sv.acervoTermo = termo.value; redesenharPainelSv(); const el = document.querySelector("[data-sv-acervo-termo]"); if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } };
  clique("[data-sv-acervo]", () => verNoAcervo(sv.aberto.cliente_nome || ""));
  clique("[data-sv-arquivo]", (b) => abrirArquivoDoServico(b.dataset.svArquivo));
  clique("[data-sv-arquivo-mais]", (b) => menuDoArquivoDoServico(b, b.dataset.svArquivoMais));
  clique("[data-sv-pessoa]", (b) => menuDePessoas(b));
  clique("[data-sv-pessoa-tirar]", (b) => mudarEquipeDoServico(sv.aberto.equipe.map((p) => p.id).filter((id) => id !== Number(b.dataset.svPessoaTirar))));
  clique("[data-sv-agendar]", () => agendarDoServico(sv.aberto));
  const nota = document.querySelector("[data-sv-nota]");
  if (nota) nota.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); anotarNoServico(nota.value); } };
  clique("[data-sv-alca]", () => { sv.largo = !sv.largo; desenharServicos(); });
  document.querySelectorAll("[data-sv-campo]").forEach((el) => {
    const guardar = () => { sv.form[el.dataset.svCampo] = el.dataset.svCampo === "cadastro_id" ? (Number(el.value) || null) : el.value; };
    el.oninput = guardar;
    el.onchange = guardar;
    if (el.tagName === "INPUT") el.onkeydown = (e) => { if (e.key === "Enter") { guardar(); salvarServico(); } };
  });
  clique("[data-sv-chip]", (b) => {
    const id = Number(b.dataset.svChip);
    sv.form.equipe = sv.form.equipe.includes(id) ? sv.form.equipe.filter((x) => x !== id) : sv.form.equipe.concat([id]);
    b.classList.toggle("on", sv.form.equipe.includes(id));
  });
  clique("[data-sv-salvar]", () => salvarServico());
  clique("[data-sv-cancelar]", () => { sv.form = null; desenharServicos(); });
}

/* So o painel, para a busca do Acervo nao perder o foco a cada letra. */
function redesenharPainelSv() {
  const velho = document.querySelector("#sv-tela .acervo-painel");
  if (!velho) return;
  velho.outerHTML = painelDoTrabalho();
  ligarServicos();
}

/* ------------------------------------------------------------ acoes */

function menuDoServico(botao, s) {
  if (!s) return;
  const itens = [
    { rotulo: "Abrir a pasta", icone: "folder_open", acao: () => abrirServico(s.id) },
    { rotulo: "Editar", icone: "edit", acao: () => { sv.form = formDoServico(s); desenharServicos(); } },
    "-",
  ];
  sv.status.filter((x) => x.valor !== s.status).forEach((x) => {
    itens.push({ rotulo: "Marcar: " + x.rotulo, icone: x.valor === "concluido" ? "task_alt" : "flag", acao: () => mudarStatusDoServico(s.id, x.valor) });
  });
  itens.push("-", { rotulo: "Apagar", icone: "delete", perigo: true, acao: () => apagarServico(s) });
  menuNaLinha(botao, itens);
}

async function salvarServico() {
  const f = sv.form;
  if (!f || sv.salvando) return;
  if (!f.nome.trim()) { avisoCert("o serviço precisa de um nome"); return; }
  sv.salvando = true;
  const r = await fetch("/api/servicos", { method: "POST", headers: SV_JSON, body: JSON.stringify({ id: f.id, dados: f }) });
  sv.salvando = false;
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const s = await r.json();
  sv.form = null;
  if (f.id) {
    avisoCert("serviço guardado");
    if (sv.visao === "trabalho") { sv.aberto = s; return mostrarServicos("trabalho"); }
    return mostrarServicos("pastas");
  }
  avisoCert("serviço aberto: " + s.nome);
  abrirServico(s.id);
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

function menuDePessoas(botao) {
  const s = sv.aberto;
  const ja = new Set(s.equipe.map((p) => p.id));
  const pessoas = sv.clientes.filter((c) => (c.tipo === "colaborador" || c.tipo === "socio") && !ja.has(c.id));
  if (!pessoas.length) {
    avisoCert(sv.clientes.some((c) => c.tipo === "colaborador" || c.tipo === "socio")
      ? "toda a equipe já está nesta pasta"
      : "ninguém na equipe ainda — cadastre as pessoas em Cadastros > Equipe");
    return;
  }
  menuNaLinha(botao, pessoas.map((p) => ({ rotulo: p.nome, icone: "person", acao: () => mudarEquipeDoServico(s.equipe.map((x) => x.id).concat([p.id])) })));
}

async function abrirLigarDoAcervo() {
  if (!sv.acervo) {
    try { sv.acervo = (await (await fetch("/api/biblioteca")).json()).documentos || []; } catch (err) { sv.acervo = []; }
  }
  sv.ligar = true;
  sv.form = null;
  sv.acervoTermo = "";
  desenharServicos();
  const el = document.querySelector("[data-sv-acervo-termo]");
  if (el) el.focus();
}

async function ligarDocumentoAoServico(sha1) {
  const doc = (sv.acervo || []).find((d) => d.sha1 === sha1);
  if (!doc) return;
  const r = await fetch("/api/servicos/" + sv.aberto.id + "/vincular", { method: "POST", headers: SV_JSON, body: JSON.stringify({ sha1: sha1, nome: doc.nome }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  avisoCert(doc.nome + " ligado à pasta");
  const rr = await fetch("/api/servicos/" + sv.aberto.id);
  if (rr.ok) sv.aberto = await rr.json();
  redesenharPainelSv();
  const principal = document.querySelector("#sv-tela .acervo-principal");
  if (principal) { principal.outerHTML = corpoDoTrabalho(); ligarServicos(); }
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

function agendarDoServico(s) {
  if (!s) return;
  ag.visao = "semana";
  ag.painel = "form";
  ag.form = Object.assign(compromissoEmBranco("compromisso"), { cadastro_id: s.cadastro_id || null, titulo: s.nome });
  mostrarAgenda("semana");
}

