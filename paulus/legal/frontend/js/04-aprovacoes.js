/* --------------------------------------------------------- aprovacoes */
/*
   A regra central do manual mora aqui: nada com efeito externo acontece sem o
   sim de uma pessoa. A fila e o lugar comum onde essas acoes param.
*/

/*
   A fila de aprovacoes (docs/ui/03-telas-desktop.md, A11), na medida de
   leitura de Servicos e da caixa de E-mail (1080px, 12-servicos.css): uma
   pagina so, sem coluna ao lado. Em cima, o que espera o seu sim; embaixo,
   o Historico do que ja foi decidido hoje. O detalhe de um pedido e as
   regras de alcada abrem em pop-up (16-dialogos.js).

   O servidor guarda os pedidos pendentes e os decididos hoje. As regras de
   alcada sao a autonomia do assistente, a mesma de Configuracoes: ligada, a
   acao acontece direto; desligada, para na fila.
*/

// Quantas decisoes o Historico mostra de cada vez.
const AP_HISTORICO_PASSO = 8;

const aprov = {
  pendentes: [], hoje: [], marcados: new Set(), aberto: null,
  visao: "fila", filtro: "", regras: null, histMostra: AP_HISTORICO_PASSO,
};

const ICONE_CATEGORIA = { organizar: "drive_file_move", arquivo: "folder", email: "mail", assinatura: "draw", permissao: "shield_person", financeiro: "payments" };
const CHAVE_DA_CATEGORIA = { organizar: "organizar_mover", assinatura: "assinar", email: "enviar_mensagem" };
const ICONE_REGRA = { ler_pastas: "folder_open", organizar_mover: "drive_file_move", assinar: "draw", enviar_mensagem: "mail", modelo_nuvem: "upload" };
const VERBO_APROVAR = { organizar: "Aprovar e mover", email: "Aprovar e enviar", assinatura: "Aprovar e assinar", financeiro: "Aprovar e pagar", permissao: "Aprovar" };

/* Para onde a pessoa vai depois do sim, por tipo de pedido. A fila nao e o
   fim do trabalho: quem pediu uma assinatura quer ver o documento assinado,
   quem organizou quer ver as pastas. Cada entrada recebe o que o servidor
   devolveu para aquele pedido ({id, categoria, resultado, desfecho}) e
   devolve true se levou a pessoa para outro lugar. Tipo sem entrada fica
   na fila, com o aviso de aprovado - e o padrao. */
const DEPOIS_DE_APROVAR = {
  assinatura: (feito) => abrirAssinado(feito.desfecho),
  organizar: () => organizarDesfecho(),
};

function dataHoraCurta(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return String(iso);
  const hoje = new Date();
  const hora = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  const mesmoDia = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (mesmoDia(d, hoje)) return "hoje " + hora;
  const ontem = new Date(hoje);
  ontem.setDate(hoje.getDate() - 1);
  if (mesmoDia(d, ontem)) return "ontem " + hora;
  return d.getDate() + " " + MESES_CURTOS[d.getMonth()] + " " + hora;
}

/* O cabecalho: a fila e o historico moram na mesma pagina; so as regras de
   alcada tem botao, e abrem em pop-up. */
function cabecalhoAprovacoes() {
  $("acoes-tela").innerHTML = '<button class="com-icone" id="ap-regras">' + ic("tune", 16) + "Regras de alçada</button>";
  $("ap-regras").onclick = () => abrirRegrasDeAlcada();
}

/* A casca da pagina: a medida de leitura, sem painel ao lado. */
function apCasca(miolo) {
  return '<div class="acervo sem-painel ap-tela" id="ap-tela"><div class="acervo-principal sv-principal"><div class="sv-medida">' +
    miolo + "</div></div></div>";
}

async function carregarFila() {
  try {
    const d = await (await fetch("/api/aprovacoes")).json();
    aprov.pendentes = d.pendentes;
    aprov.hoje = d.hoje;
    return true;
  } catch (err) {
    $("centro").innerHTML = apCasca('<p class="nota">não consegui abrir: ' + esc(String(err)) + "</p>");
    return false;
  }
}

async function mostrarAprovacoes() {
  abrirTela("Aprovações", { cheia: true });
  aprov.visao = "fila";
  aprov.histMostra = AP_HISTORICO_PASSO;
  cabecalhoAprovacoes();
  $("centro").innerHTML = apCasca(esqueleto("lista"));
  if (!(await carregarFila())) return;
  if (!aprov.regras) {
    try { aprov.regras = await (await fetch("/api/preferencias")).json(); } catch (err) { aprov.regras = null; }
  }
  desenharAprovacoes();
  atualizarPostura();
  // Quem chega de outra tela apontando um pedido (o organizador) ve o
  // detalhe dele aberto.
  if (aprov.aberto) {
    const id = aprov.aberto;
    aprov.aberto = null;
    verPedido(id);
  }
}

/* O Historico nao e mais outra tela: e a secao de baixo da mesma pagina.
   Quem chamava a tela de Historico cai nela, ja rolada ate la. */
async function mostrarHistoricoDeAprovacoes() {
  await mostrarAprovacoes();
  const secao = document.getElementById("ap-historico");
  if (secao) secao.scrollIntoView({ block: "start" });
}

/* As regras de alcada abrem em pop-up sobre a fila. Quem chama de fora
   (Cadastros) abre a fila por baixo. */
async function mostrarRegrasDeAlcada() {
  if (!document.getElementById("ap-tela")) await mostrarAprovacoes();
  abrirRegrasDeAlcada();
}

function quemPediu(nome) {
  const assistente = !nome || nome === "Assistente" || nome === "PAULUS";
  const iniciais = (nome || "").trim().split(/\s+/).map((x) => x[0] || "").slice(0, 2).join("").toUpperCase();
  return '<span class="quem">' +
    (assistente ? '<span class="avatar-p">P</span>' : '<span class="avatar-mini">' + esc(iniciais || "?") + "</span>") +
    "<span>" + esc(nome || "Assistente") + "</span></span>";
}

function metaDoPedido(p) {
  const partes = [p.categoria_rotulo].concat(p.etiquetas || []);
  if (!p.reversivel) partes.push("sem desfazer");
  return partes.filter(Boolean).join(" · ");
}

function esperandoHa(iso) {
  return quando(iso).replace(/^há /, "");
}

function autonomiaAtual() {
  const r = aprov.regras;
  if (!r) return {};
  return ((r.preferencias || r).autonomia) || {};
}

function desenharAprovacoes() {
  const todos = aprov.pendentes;
  const categorias = [...new Set(todos.map((p) => p.categoria))];
  if (aprov.filtro && !categorias.includes(aprov.filtro)) aprov.filtro = "";
  for (const id of [...aprov.marcados]) if (!todos.some((p) => p.id === id)) aprov.marcados.delete(id);
  const n = todos.length;
  $("conversa-meta").textContent = (n ? n + " esperando você" : "nada esperando você") + " · nada sai sem aprovação";

  const antes = document.querySelector("#ap-tela .sv-principal");
  const topo = antes ? antes.scrollTop : 0;
  $("centro").innerHTML = apCasca(apFila(categorias) + apHistorico());
  const novo = document.querySelector("#ap-tela .sv-principal");
  if (novo && topo) novo.scrollTop = topo;
  if (conteudoNovo("aprovacoes:" + aprov.filtro)) {
    entraConteudo($("centro").firstElementChild);
    entraLista($("centro"), ".tabela-linha");
  }
  ligarAprovacoes();
}

/* O cartao de cima: o que espera o seu sim. */
function apFila(categorias) {
  const todos = aprov.pendentes;
  const lista = aprov.filtro ? todos.filter((p) => p.categoria === aprov.filtro) : todos;
  const n = todos.length, m = aprov.marcados.size;

  // Filtro por tipo so quando ha mais de um tipo na fila.
  const chips = categorias.length > 1
    ? '<span class="visoes">' +
      [["", "Tudo"]].concat(categorias.map((c) => [c, (todos.find((p) => p.categoria === c) || {}).categoria_rotulo || c])).map(([v, r]) => {
        const classe = v === aprov.filtro ? "ativa" : "";
        return '<button class="' + classe + '" data-filtro-ap="' + esc(v) + '">' + esc(r) + "</button>";
      }).join("") + "</span>"
    : "";
  const acoes = '<span class="direita">' +
    '<button class="perigo com-icone" id="ap-recusar"' + (m ? "" : " disabled") + ">" + ic("close", 16) + "Recusar" + (m ? " · " + m : "") + "</button>" +
    '<button class="ap-sim com-icone" id="ap-aprovar"' + (m ? "" : " disabled") + ">" + ic("done_all", 16) + "Aprovar" + (m ? " · " + m : "") + "</button></span>";

  const linhas = lista.length
    ? lista.map(linhaPedido).join("")
    : (n
      ? '<p class="nota">Nada nesta categoria.</p>'
      : '<div class="painel-vazio ap-vazio"><h3>Nada esperando você</h3><p>' +
        "Quando o assistente quiser fazer algo com efeito fora do programa — mover arquivos em lote, " +
        "assinar, enviar mensagem — o pedido para aqui e espera o seu sim.</p></div>");

  const todosMarcados = n > 0 && m === n;
  const classe = "marcar" + (todosMarcados ? " on" : "");
  return '<section class="tabela-cartao ap-cartao" id="ap-fila">' +
    '<div class="tabela-barra"><span class="ap-titulo">Esperando você</span>' +
    (n ? '<span class="ap-conta">' + n + "</span>" + chips + acoes : "") + "</div>" +
    (n
      ? '<div class="tabela-cabecalho colunas-fila"><span class="' + classe + '" id="ap-todos" role="checkbox" aria-checked="' +
        (todosMarcados ? "true" : "false") + '" title="Marcar todos">' + ic("check", 12) + "</span>" +
        '<span>O que precisa do seu sim</span><span>Pedido por</span><span>Esperando há</span><span class="ap-direita">Ação</span></div>'
      : "") +
    '<div class="tabela-corpo">' + linhas + "</div>" +
    (n
      ? '<div class="tabela-rodape"><span>Clique num pedido para ver o que vai sair e se dá para desfazer</span>' +
        '<span class="cresce"></span><span>Aprovado ou recusado, vai para o Histórico, logo abaixo</span></div>'
      : "") +
    "</section>";
}

function linhaPedido(p) {
  const marcado = aprov.marcados.has(p.id);
  const classe = "tabela-linha colunas-fila" + (marcado ? " escolhida" : "");
  return '<div class="' + classe + '" data-pedido="' + esc(p.id) + '" title="Ver o pedido">' +
    '<span class="marcar' + (marcado ? " on" : "") + '" data-marcar="' + esc(p.id) + '" role="checkbox" aria-checked="' +
    (marcado ? "true" : "false") + '">' + ic("check", 12) + "</span>" +
    '<span class="nome-doc"><span class="caixa-tipo">' + ic(ICONE_CATEGORIA[p.categoria] || "verified", 18) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(p.titulo) + "</b><small>" +
    (p.vence_hoje ? '<span class="ap-vence">vence hoje</span> · ' : "") + esc(metaDoPedido(p)) + "</small></span></span>" +
    quemPediu(p.pedido_por) +
    '<span class="espera">' + esc(esperandoHa(p.criado_em)) + "</span>" +
    '<span class="acoes-linha direita"><button class="ap-nao" data-recusar="' + esc(p.id) + '">Recusar</button>' +
    '<button class="ap-sim" data-aprovar="' + esc(p.id) + '">Aprovar</button></span></div>';
}

/* ----------------------------------------------------------- historico */
/* O servidor devolve as decisoes de hoje; e o que a secao mostra, dizendo
   isso. As mais recentes primeiro, de oito em oito. */

function seloDecisao(p) {
  if (p.estado === "aprovado") return '<span class="pilula-estado ok"><i></i>Aprovado</span>';
  if (p.estado === "recusado") return '<span class="pilula-estado prazo"><i></i>Recusado</span>';
  return '<span class="pilula-estado prazo"><i></i>Não deu</span>';
}

function apDecididos() {
  return aprov.hoje.slice().sort((a, b) => (b.decidido_em || "").localeCompare(a.decidido_em || ""));
}

function apHistorico() {
  const lista = apDecididos();
  const vistos = lista.slice(0, aprov.histMostra);
  const aprovados = lista.filter((p) => p.estado === "aprovado").length;
  const recusados = lista.filter((p) => p.estado === "recusado").length;
  const falhas = lista.length - aprovados - recusados;

  const linhas = vistos.length ? vistos.map((p) =>
    '<div class="tabela-linha ap-colunas-historico" data-decidido="' + esc(p.id) + '" title="Ver a decisão">' +
      '<span class="nome-doc"><span class="caixa-tipo">' + ic(ICONE_CATEGORIA[p.categoria] || "verified", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(p.titulo) + "</b><small>" +
      esc([p.categoria_rotulo, p.resultado].filter(Boolean).join(" · ")) + "</small></span></span>" +
      quemPediu(p.pedido_por) +
      '<span class="espera">' + esc(dataHoraCurta(p.criado_em)) + "</span>" +
      '<span class="espera">' + esc(dataHoraCurta(p.decidido_em)) + "</span>" +
      '<span class="acoes-linha direita">' + seloDecisao(p) + "</span></div>").join("")
    : '<p class="nota">Nenhuma decisão hoje. O que você aprovar ou recusar aparece aqui, com o resultado.</p>';

  const resumo = lista.length
    ? [aprovados ? plural(aprovados, "aprovado") : "", recusados ? plural(recusados, "recusado") : "",
      falhas ? falhas + " não " + (falhas === 1 ? "deu" : "deram") : ""].filter(Boolean).join(" · ")
    : "";
  const faltam = lista.length - vistos.length;
  return '<section class="tabela-cartao ap-cartao" id="ap-historico">' +
    '<div class="tabela-barra"><span class="ap-titulo">Histórico</span>' +
    '<span class="nota-barra">o que foi decidido hoje</span>' +
    (resumo ? '<span class="direita nota-barra">' + resumo + "</span>" : "") + "</div>" +
    (lista.length
      ? '<div class="tabela-cabecalho ap-colunas-historico"><span>Pedido</span><span>Pedido por</span><span>Pedido em</span>' +
        '<span>Decidido em</span><span class="ap-direita">Decisão</span></div>'
      : "") +
    '<div class="tabela-corpo">' + linhas + "</div>" +
    (lista.length
      ? '<div class="tabela-rodape"><span>' + (faltam ? "mostrando " + vistos.length + " de " + lista.length + " decisões de hoje"
        : plural(lista.length, "decisão", "decisões") + " hoje") + "</span>" + '<span class="cresce"></span>' +
        (faltam ? '<button class="mais" id="ap-historico-mais">Ver mais ' + Math.min(faltam, AP_HISTORICO_PASSO) + "</button>" : "") +
        "</div>"
      : "") +
    "</section>";
}

function ligarAprovacoes() {
  const centro = $("centro");
  centro.querySelectorAll("[data-filtro-ap]").forEach((b) => {
    b.onclick = () => { aprov.filtro = b.dataset.filtroAp; desenharAprovacoes(); };
  });
  centro.querySelectorAll("[data-marcar]").forEach((c) => {
    c.onclick = (e) => {
      e.stopPropagation();
      const id = c.dataset.marcar;
      if (aprov.marcados.has(id)) aprov.marcados.delete(id); else aprov.marcados.add(id);
      desenharAprovacoes();
    };
  });
  const todos = $("ap-todos");
  if (todos) todos.onclick = () => {
    if (!aprov.pendentes.length) return;
    aprov.marcados = aprov.marcados.size === aprov.pendentes.length ? new Set() : new Set(aprov.pendentes.map((p) => p.id));
    desenharAprovacoes();
  };
  centro.querySelectorAll("[data-pedido]").forEach((l) => {
    l.onclick = () => verPedido(l.dataset.pedido);
  });
  centro.querySelectorAll("[data-decidido]").forEach((l) => {
    l.onclick = () => verDecidido(l.dataset.decidido);
  });
  centro.querySelectorAll("[data-aprovar]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); decidirPedidos([b.dataset.aprovar], true); };
  });
  centro.querySelectorAll("[data-recusar]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); decidirPedidos([b.dataset.recusar], false); };
  });
  const aprovar = $("ap-aprovar"), recusar = $("ap-recusar");
  if (aprovar) aprovar.onclick = () => decidirPedidos(Array.from(aprov.marcados), true);
  if (recusar) recusar.onclick = () => decidirPedidos(Array.from(aprov.marcados), false);
  const mais = $("ap-historico-mais");
  if (mais) mais.onclick = () => { aprov.histMostra += AP_HISTORICO_PASSO; desenharAprovacoes(); };
}

/* ----------------------------------------------------- o pedido aberto */
/* O que vai sair, o efeito, se da para desfazer - num pop-up, e nao mais na
   coluna ao lado. Aprovar daqui passa pela mesma confirmacao da fila. */

function apSaida(p) {
  const dados = p.dados || {};
  const arquivos = Array.isArray(dados.arquivos) ? dados.arquivos : (Array.isArray(dados.caminhos) ? dados.caminhos : []);
  const para = Array.isArray(dados.para) ? dados.para : (Array.isArray(dados.destinatarios) ? dados.destinatarios : (dados.para ? [dados.para] : []));
  if (!arquivos.length && !para.length) return "";
  // Caminho inteiro vira so o nome do arquivo: a pasta esta no resumo.
  const nomeDe = (x) => {
    const bruto = typeof x === "string" ? x : (x.nome || x.arquivo || x.caminho || x.email || "");
    return bruto.includes("@") ? bruto : bruto.split(/[\\/]/).pop();
  };
  const itens = para.slice(0, 8).map((x) => '<div class="arquivo-painel">' + ic("mail", 16) + "<span>" + esc(nomeDe(x)) + "</span></div>")
    .concat(arquivos.slice(0, 8).map((x) => {
      const nome = nomeDe(x);
      return '<div class="arquivo-painel">' + glifo(nome) + "<span>" + esc(nome) + "</span></div>";
    }));
  const resto = Math.max(0, para.length - 8) + Math.max(0, arquivos.length - 8);
  return '<div class="ap-saida"><span class="sv-kicker">O que vai sair · ' +
    (para.length ? plural(para.length, "destinatário") : plural(arquivos.length, "arquivo")) + "</span>" +
    '<div class="ap-saida-lista">' + itens.join("") + (resto ? '<span class="nota-barra">e mais ' + resto + "</span>" : "") + "</div></div>";
}

async function verPedido(id) {
  const p = aprov.pendentes.find((x) => x.id === id);
  if (!p) return;
  const chave = CHAVE_DA_CATEGORIA[p.categoria];
  const regra = chave && autonomiaAtual()[chave]
    ? "o assistente pode fazer isso sem pedir"
    : "você aprova · o assistente não faz isso sozinho";
  let recusar = false;
  const espera = dialogo({
    titulo: p.titulo, contexto: "Aprovações › " + (p.categoria_rotulo || "pedido"),
    classe: "dialogo-ver ap-dialogo", larga: true, cancelar: "Fechar",
    confirmar: VERBO_APROVAR[p.categoria] || "Aprovar", sucesso: true,
    html: (p.resumo ? '<p class="ap-resumo">' + esc(p.resumo) + "</p>" : "") +
      fichaDoDialogo([
        ["Pedido por", p.pedido_por || "Assistente"],
        ["Pedido em", dataHoraCurta(p.criado_em)],
        p.prazo ? ["Prazo", dataLonga(p.prazo) + (p.vence_hoje ? " · vence hoje" : "")] : null,
        ["Efeito", p.reversivel ? "dá para desfazer" : "externo · sem desfazer depois"],
        ["Regra de alçada", regra],
        ["Se recusar", "encerra o pedido · nada é executado"],
      ]) + apSaida(p),
    rodape: '<button type="button" class="perigo com-icone" id="ap-dlg-recusar">' + ic("close", 16) + "Recusar</button>",
  });
  const botao = document.getElementById("ap-dlg-recusar");
  if (botao) botao.onclick = () => { recusar = true; if (dialogoAberto) dialogoAberto.fechar(null); };
  const r = await espera;
  if (r && r.ok) decidirPedidos([id], true);
  else if (recusar) decidirPedidos([id], false);
}

/* A decisao aberta: a linha do tempo do pedido, so leitura. */
function verDecidido(id) {
  const p = aprov.hoje.find((x) => x.id === id);
  if (!p) return;
  const decisao = p.estado === "aprovado" ? "aprovado" : (p.estado === "recusado" ? "recusado" : "aprovado, mas não deu");
  dialogo({
    titulo: p.titulo, contexto: "Aprovações › Histórico",
    classe: "dialogo-ver ap-dialogo ap-dialogo-leitura", larga: true, confirmar: "Fechar",
    html: (p.resumo ? '<p class="ap-resumo">' + esc(p.resumo) + "</p>" : "") +
      fichaDoDialogo([
        ["Pedido por", p.pedido_por || "Assistente"],
        ["Pedido em", dataHoraCurta(p.criado_em)],
        ["Decisão", decisao + " · " + dataHoraCurta(p.decidido_em)],
        ["Resultado", p.resultado || (p.estado === "recusado" ? "nada foi executado" : "")],
      ]),
  });
}

/* Ctrl+Enter na fila: aprova o que esta marcado. Sem nada marcado nao faz
   nada calado - dizer "marque primeiro" e melhor que parecer que travou. */
function aprovarMarcados() {
  const ids = Array.from(aprov.marcados);
  if (!ids.length) { avisoCert("marque os pedidos que você quer aprovar"); return; }
  decidirPedidos(ids, true);
}

async function decidirPedidos(ids, aprovar) {
  if (!ids.length) return;
  const quais = ids.map((id) => aprov.pendentes.find((p) => p.id === id)).filter(Boolean);
  const semVolta = quais.filter((p) => !p.reversivel);

  /* Um pedido: o titulo diz qual. Varios: quantos, e quais nao tem volta.
     Aprovar e o sim - botao verde; so recusar e que e vermelho. */
  const um = quais.length === 1 ? quais[0] : null;
  const nome = (p) => "“" + (p.titulo || "pedido") + "”";
  let titulo, texto;
  if (aprovar) {
    titulo = um ? "Aprovar " + nome(um) + "?" : "Aprovar " + ids.length + " pedidos?";
    texto = um ? "Ao aprovar, eu faço isso agora." : "Ao aprovar, eu faço os " + ids.length + " agora, um depois do outro.";
    if (um && semVolta.length) texto += "\nDepois de feito, não tem como desfazer — confira antes.";
    else if (semVolta.length === quais.length && quais.length > 1) texto += "\nNenhum deles tem como ser desfeito depois — confira antes.";
    else if (semVolta.length) texto += "\nNão têm como ser desfeitos depois: " + semVolta.map(nome).join(", ") + ".";
  } else {
    titulo = um ? "Recusar " + nome(um) + "?" : "Recusar " + ids.length + " pedidos?";
    texto = "Nada é feito: " + (um ? "o pedido sai" : "os pedidos saem") + " da fila e " + (um ? "fica registrado" : "ficam registrados") + " no Histórico.";
  }
  if (!(await confirmar({ titulo: titulo, contexto: "Aprovações", texto: texto, confirmar: aprovar ? "Aprovar" : "Recusar", perigo: !aprovar, sucesso: aprovar }))) return;

  atualizarSelo(true);
  try {
    const r = await fetch("/api/aprovacoes/decidir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: ids, aprovar: aprovar }),
    });
    const d = await r.json();
    aprov.pendentes = d.pendentes;
    aprov.hoje = d.hoje;
    aprov.marcados = new Set();
    if (document.getElementById("ap-tela")) desenharAprovacoes();
    if (d.falhas.length) {
      avisoCert("Não consegui em " + d.falhas.length + ": " + d.falhas.map((f) => f.motivo).join("; "));
    } else {
      avisoCert(aprovar ? plural(ids.length, "pedido") + (ids.length === 1 ? " aprovado" : " aprovados") : plural(ids.length, "pedido") + (ids.length === 1 ? " recusado" : " recusados"));
    }
    carregarStatus();
    contarPendencias();
    // O aprovado nao termina na fila: a pessoa vai ver o que foi feito (a
    // assinatura abre o documento assinado; organizar volta as pastas, com
    // o desfazer a mao). Com varios aprovados, vale o primeiro que tem para
    // onde ir; o resto fica no Historico.
    if (aprovar) {
      for (const f of d.feitos || []) {
        const categoria = f.categoria || ((quais.find((p) => p.id === f.id) || {}).categoria);
        const ir = DEPOIS_DE_APROVAR[categoria];
        if (ir && (await ir(f))) break;
      }
    }
  } catch (err) {
    avisoCert("Falha ao decidir: " + err);
  } finally {
    atualizarSelo(false);
  }
}

/* ------------------------------------------------------ regras de alcada */
/* A autonomia do assistente, a mesma de Configuracoes, num pop-up sobre a
   fila. Ligada, a acao acontece direto; desligada, para na fila. O padrao e
   sempre o mais cauteloso. Mexer nas chaves nao grava nada: so o Salvar. */

function apLinhaDeRegra(o, ligada) {
  const estadoTexto = o.travada ? "indisponível" : (ligada ? "acontece direto" : "para na fila");
  return '<div class="ap-regra' + (o.travada ? " travada" : "") + '">' +
    '<span class="caixa-tipo">' + ic(ICONE_REGRA[o.chave] || "verified", 18) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(o.titulo) + "</b><small>" + esc(o.explica || "") + "</small></span>" +
    '<span class="ap-regra-estado">' + estadoTexto + "</span>" +
    (o.travada ? "<span></span>"
      : '<button type="button" class="interruptor-min' + (ligada ? " on" : "") + '" data-ap-ligar="' + esc(o.chave) +
        '" role="switch" aria-checked="' + (ligada ? "true" : "false") + '" aria-label="' + esc(o.titulo) + '"><span class="chave"></span></button>') +
    "</div>";
}

async function abrirRegrasDeAlcada() {
  if (!aprov.regras) {
    try { aprov.regras = await (await fetch("/api/preferencias")).json(); } catch (err) { aprov.regras = null; }
  }
  if (!aprov.regras) { avisoCert("não consegui abrir as regras de alçada"); return; }
  const opcoes = aprov.regras.autonomia_opcoes || [];
  const antes = Object.assign({}, autonomiaAtual());
  const escolha = Object.assign({}, antes);
  const lista = () => opcoes.map((o) => apLinhaDeRegra(o, Boolean(escolha[o.chave]))).join("");

  const espera = dialogo({
    titulo: "Regras de alçada", contexto: "Aprovações › quem aprova o quê",
    classe: "dialogo-ver ap-dialogo-regras", larga: true, confirmar: "Salvar",
    texto: "Ligada, a ação acontece direto, sem pedir. Desligada, para na fila e espera o seu sim. " +
      "O padrão é sempre o mais cauteloso.",
    html: '<div class="ap-regras" id="ap-regras-lista">' + lista() + "</div>",
    rodape: '<button type="button" id="ap-regras-padrao">Restaurar padrão</button>',
  });
  const caixa = document.getElementById("ap-regras-lista");
  const padrao = document.getElementById("ap-regras-padrao");
  const ligar = () => {
    if (!caixa) return;
    caixa.querySelectorAll("[data-ap-ligar]").forEach((b) => {
      b.onclick = () => {
        escolha[b.dataset.apLigar] = !escolha[b.dataset.apLigar];
        caixa.innerHTML = lista();
        ligar();
        const mesmo = caixa.querySelector('[data-ap-ligar="' + b.dataset.apLigar + '"]');
        if (mesmo) mesmo.focus();
      };
    });
  };
  ligar();
  if (padrao) padrao.onclick = () => {
    opcoes.forEach((o) => { if (!o.travada) escolha[o.chave] = Boolean(o.padrao); });
    caixa.innerHTML = lista();
    ligar();
  };

  const r = await espera;
  if (!r || !r.ok) return;
  const mudou = opcoes.some((o) => Boolean(escolha[o.chave]) !== Boolean(antes[o.chave]));
  if (!mudou) return;
  const pr = aprov.regras.preferencias || aprov.regras;
  const autonomia = Object.assign({}, pr.autonomia || {}, escolha);
  try {
    const resp = await fetch("/api/preferencias", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ autonomia: autonomia }),
    });
    if (!resp.ok) throw new Error(await erroDe(resp));
    pr.autonomia = autonomia;
    avisoCert("regras gravadas: valem para os próximos pedidos");
  } catch (err) {
    avisoCert("não consegui gravar: " + err);
  }
}

/* O menu mostra quantos pedidos esperam - a fila nao serve se ninguem ve. */
async function contarPendencias() {
  try {
    const d = await (await fetch("/api/aprovacoes")).json();
    const n = d.pendentes.length;
    document.querySelectorAll('[data-destino="aprovacoes"] .conta').forEach((c) => {
      c.textContent = n ? String(n) : "";
      c.hidden = !n;
    });
  } catch (err) { /* sem numero e melhor que numero errado */ }
}

setInterval(contarPendencias, 8000);
