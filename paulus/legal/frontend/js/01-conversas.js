/* ----------------------------------------------------------- trabalhos */

let gruposConhecidos = [];

async function carregarTrabalhos() {
  const r = await fetch("/api/trabalhos");
  const d = await r.json();
  gruposConhecidos = d.nomes_de_grupo || [];
  estado.recentes = d.grupos.flatMap((g) => g.trabalhos);

  /* A lista mora no Assistente: tres recentes e "Ver mais" com todas. */
  if ($("conversa-col").classList.contains("vazia")) desenharRecentes();
}

/* ------------------------------------------------------- menu de conversa */

function fecharMenu() {
  const aberto = document.querySelector(".menu-conversa");
  if (aberto) aberto.remove();
}

document.addEventListener("click", fecharMenu);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharMenu(); });

function abrirMenu(linha) {
  fecharMenu();
  const id = linha.dataset.id;
  const titulo = linha.dataset.titulo;
  const grupoAtual = linha.dataset.grupo;

  const menu = document.createElement("div");
  menu.className = "menu-conversa";
  menu.innerHTML =
    '<button data-a="renomear">Renomear</button>' +
    '<button data-a="grupo">Mover para grupo<span class="seta">›</span></button>' +
    '<button data-a="duplicar">Duplicar</button>' +
    '<div class="menu-risco"></div>' +
    '<button data-a="apagar" class="perigo">Apagar</button>';

  linha.appendChild(menu);
  menu.onclick = (e) => e.stopPropagation();

  menu.querySelector('[data-a="renomear"]').onclick = () => { fecharMenu(); renomearConversa(id, titulo); };

  menu.querySelector('[data-a="grupo"]').onclick = async () => {
    fecharMenu();
    const novo = await perguntar({
      titulo: "Grupo da conversa", contexto: "Assistente › " + titulo,
      campo: { rotulo: "Nome do grupo", valor: grupoAtual, placeholder: "sem grupo", icone: "folder", sugestoes: gruposConhecidos, obrigatorio: false,
               dica: "Vazio tira a conversa do grupo. Um grupo novo nasce com o nome que você escrever." },
      confirmar: "Guardar",
    });
    if (novo === null) return;
    fetch("/api/trabalhos/" + id + "/grupo", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grupo: novo.trim() }),
    }).then(carregarTrabalhos);
  };

  menu.querySelector('[data-a="duplicar"]').onclick = async () => {
    fecharMenu();
    const r = await fetch("/api/trabalhos/" + id + "/duplicar", { method: "POST" });
    const copia = await r.json();
    await carregarTrabalhos();
    abrirTrabalho(copia.id);
  };

  menu.querySelector('[data-a="apagar"]').onclick = async () => {
    fecharMenu();
    if (!(await confirmar({ titulo: "Apagar esta conversa?", contexto: "Assistente › " + titulo, texto: "A conversa sai da lista. " + LIXEIRA_TEXTO, confirmar: "Apagar", perigo: true }))) return;
    const r = await fetch("/api/trabalhos/" + id, { method: "DELETE" });
    if (id === estado.trabalhoId) $("nova").click();
    else carregarTrabalhos();
    avisarLixeira(r, () => carregarTrabalhos());
  };
}

async function abrirTrabalho(id) {
  const r = await fetch("/api/trabalhos/" + id);
  if (!r.ok) return;
  $("compositor").hidden = false;
  estado.trabalho = await r.json();
  estado.trabalhoId = id;
  desenharTrabalho();
  carregarTrabalhos();
}

$("nova").onclick = () => {
  estado.trabalhoId = null;
  estado.trabalho = null;
  definirEscopo([]);
  $("compositor").hidden = false;
  $("conversa-titulo").textContent = "Nova conversa";
  $("apagar").hidden = true;
  $("exportar-conversa").hidden = true;
  $("centro").innerHTML = exemplos();
  $("centro").classList.remove("prosa");
  $("conversa-col").classList.remove("tela-dupla", "tela-cheia");
  $("lista-conversas").hidden = true;
  $("acoes-tela").innerHTML = "";
  $("nav-tela").innerHTML = "";
  mostrarLateral(false);
  ligarExemplos();
  desenharAtividade([]);
  carregarTrabalhos();
  marcarDestino("conversa");
  fecharFlutuante();
  atualizarPostura();
  $("pedido").focus();
};

$("apagar").onclick = async () => {
  if (!estado.trabalhoId) return;
  if (!(await confirmar({ titulo: "Apagar esta conversa?", contexto: "Assistente › " + $("conversa-titulo").textContent, texto: "A conversa sai da lista. " + LIXEIRA_TEXTO, confirmar: "Apagar", perigo: true }))) return;
  const r = await fetch("/api/trabalhos/" + estado.trabalhoId, { method: "DELETE" });
  $("nova").click();
  avisarLixeira(r, (d) => { carregarTrabalhos(); if (d && d.restaurado) abrirTrabalho(d.restaurado); });
};

function exemplos() {
  return "";   /* o estado vazio vive no compositor, nao no fluxo */
}

/* A postura da tela: inicio (saudacao, caixa de pedido, "Acontecendo agora"
   e Recentes no meio da coluna) ou conversa (a caixa desce e encosta embaixo). */
function atualizarPostura() {
  const temConversa = Boolean(
    estado.trabalhoId ||
    ($("centro") && $("centro").querySelector(".bolha-pessoa, .resposta, .catalogo, .painel, .cartao, .bancada, .dupla, .acervo, .sv-grade"))
  );
  $("conversa-col").classList.toggle("vazia", !temConversa);
  $("pedido").placeholder = temConversa
    ? "Pergunte outra coisa ou aponte outra pasta…"
    : "Peça o que precisa dos seus documentos…";
  if (!temConversa) {
    atualizarSaudacao();
    desenharRecentes();
    carregarAgora();
    $("registro").hidden = true;
  } else {
    $("agora").hidden = true;
    $("recentes").hidden = true;
    $("lista-conversas").hidden = true;
  }
}

/* Recentes: as ultimas conversas, no lugar dos exemplos de pergunta que o
   desenho nao tem. "Ver mais" abre a lista inteira aqui mesmo, embaixo. */
function desenharRecentes() {
  const alvo = $("recentes");
  const lista = (estado.recentes || []).slice(0, 3);
  if (!lista.length) { alvo.hidden = true; alvo.innerHTML = ""; return; }
  /* Aberta e a lista estar a vista - e nao uma classe na coluna, que era o
     criterio antigo e deixou de existir: com ele o botao so sabia abrir. */
  const aberta = !$("lista-conversas").hidden;
  alvo.hidden = false;
  alvo.innerHTML = '<span class="rotulo-suave">Recentes</span>' +
    lista.map((t) =>
      '<button class="recente" data-abre="' + esc(t.id) + '">' + ic("forum", 15) +
      "<span>" + esc(t.titulo) + "</span></button>").join("") +
    '<button class="ver-mais" id="recentes-mais" title="' + (aberta ? "Recolher" : "Ver todas as conversas") + '">' +
    (aberta ? ic("view_sidebar", 17) : "Ver mais" + ic("chevron_right", 16)) + "</button>";
  alvo.querySelectorAll("[data-abre]").forEach((b) => { b.onclick = () => abrirTrabalho(b.dataset.abre); });
  $("recentes-mais").onclick = () => alternarListaDeConversas(!aberta);
  if (aberta) desenharListaDeConversas();
}

/* A lista inteira, na propria tela, embaixo das recentes. Nada sobe nem se
   desloca: o inicio comeca no alto, e a lista so entra depois dele. */
function alternarListaDeConversas(abrir) {
  $("lista-conversas").hidden = !abrir;
  if (abrir) desenharListaDeConversas();
  desenharRecentes();
  if (abrir) {
    const busca = $("lc-busca");
    if (busca) busca.focus();
  }
}

const ESTADO_DA_CONVERSA = {
  executando: "trabalhando", aguardando: "esperando você", concluido: "concluída", pausado: "parada", falhou: "não deu",
};

/* A cor da etiqueta de cada estado. Parada fica cinza de proposito: ela nao
   deu errado nem deu certo - so nao terminou. */
const TOM_DO_ESTADO = {
  executando: "ok anda", aguardando: "atencao", concluido: "ok", falhou: "atencao",
};

/* A selecao da lista: segurar numa linha marca; a barra troca os filtros por
   "N selecionadas · Mover para grupo · Apagar". Vive fora do desenho para
   sobreviver ao redesenho. */
const lcSel = { escolhidos: new Set() };

function desenharListaDeConversas() {
  const caixa = $("lista-conversas");
  const termo = (caixa.dataset.termo || "").toLowerCase();
  const todas = estado.recentes || [];
  const lista = termo ? todas.filter((t) => (t.titulo || "").toLowerCase().includes(termo)) : todas;
  for (const id of [...lcSel.escolhidos]) if (!todas.some((t) => t.id === id)) lcSel.escolhidos.delete(id);

  /* A linha tem quatro coisas, e so quatro: o que e, o nome com a hora, como
     acabou e o menu. O grupo entra na segunda linha do nome, junto da hora -
     uma coluna so para ele custaria mais tela do que informa. */
  const linhas = lista.length ? lista.map((t) => {
    const quando = t.atualizado_em ? dataHoraCurta(t.atualizado_em) : "";
    const classe = "lc-linha" + (lcSel.escolhidos.has(t.id) ? " escolhida" : "");
    return '<div class="' + classe + '" data-id="' + esc(t.id) + '" data-sel="' + esc(t.id) + '" data-titulo="' + esc(t.titulo) +
      '" data-grupo="' + esc(t.grupo || "") + '">' +
      ic(t.tipo === "organizacao" ? "drive_file_move" : "forum", 17) +
      '<span class="lc-nome"><b>' + esc(t.titulo) + "</b><small>" + esc(quando) +
      (t.grupo ? " · " + esc(t.grupo) : "") + "</small></span>" +
      '<span class="estado-conversa"><span class="etiqueta ' + (TOM_DO_ESTADO[t.estado] || "") + '">' +
      (ESTADO_DA_CONVERSA[t.estado] || esc(t.estado)) + "</span></span>" +
      '<button class="lc-mais" data-lc-menu="1" title="Mais" aria-label="Mais">' + ic("more_horiz", 17) + "</button></div>";
  }).join("") : '<p class="lc-vazio">' + (termo ? "Nenhuma conversa com esse nome." : "Nenhuma conversa ainda.") + "</p>";

  const quantos = lcSel.escolhidos.size;
  const barra = quantos
    ? '<span class="cresce">' + barraDeSelecao(quantos, true,
      '<button data-lc-grupo="1">' + ic("folder", 16) + "Mover para grupo</button><span class=\"divisa-v\"></span>" +
      '<button class="botao-icone perigo" data-lc-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-lc-limpar") + "</span>"
    : '<span class="lc-conta">' + plural(todas.length, "conversa") + "</span>";
  caixa.innerHTML = '<div class="lc-cartao"><div class="lc-barra">' + barra +
    '<label class="lc-busca">' + ic("search", 15) +
    '<input type="text" id="lc-busca" placeholder="Buscar conversa…" value="' + esc(caixa.dataset.termo || "") + '"></label>' +
    '<button class="lc-recolher" id="lc-recolher" title="Recolher" aria-label="Recolher">' + ic("view_sidebar", 16) + "</button></div>" +
    linhas + "</div>";

  caixa.querySelectorAll(".lc-linha").forEach((linha) => {
    linha.onclick = () => abrirTrabalho(linha.dataset.id);
    linha.querySelector("[data-lc-menu]").onclick = (e) => { e.stopPropagation(); abrirMenu(linha); };
  });
  ligarSelecao(caixa.querySelector(".lc-cartao"), {
    linhas: ".lc-linha[data-sel]", escolhidos: lcSel.escolhidos, aoMudar: desenharListaDeConversas,
    apagar: (ids) => apagarConversasEmLote(ids),
    renomear: (id) => { const t = todas.find((x) => x.id === id); if (t) renomearConversa(id, t.titulo); },
  });
  const limparSel = caixa.querySelector("[data-lc-limpar]");
  if (limparSel) limparSel.onclick = (e) => { e.stopPropagation(); lcSel.escolhidos.clear(); desenharListaDeConversas(); };
  const apagarSel = caixa.querySelector("[data-lc-apagar]");
  if (apagarSel) apagarSel.onclick = (e) => { e.stopPropagation(); apagarConversasEmLote([...lcSel.escolhidos]); };
  const grupoSel = caixa.querySelector("[data-lc-grupo]");
  if (grupoSel) grupoSel.onclick = (e) => { e.stopPropagation(); moverConversasParaGrupo([...lcSel.escolhidos]); };
  const busca = $("lc-busca");
  let t;
  busca.oninput = (e) => {
    clearTimeout(t);
    const v = e.target.value;
    t = setTimeout(() => {
      caixa.dataset.termo = v.trim();
      const posicao = busca.selectionStart;
      desenharListaDeConversas();
      const de_novo = $("lc-busca");
      if (de_novo) { de_novo.focus(); de_novo.setSelectionRange(posicao, posicao); }
    }, 180);
  };
  $("lc-recolher").onclick = () => alternarListaDeConversas(false);
}

async function renomearConversa(id, titulo) {
  const novo = await perguntar({ titulo: "Renomear conversa", contexto: "Assistente", campo: { rotulo: "Nome", valor: titulo, icone: "forum" }, confirmar: "Renomear" });
  if (!novo || !novo.trim()) return;
  await fetch("/api/trabalhos/" + id + "/renomear", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo: novo.trim() }),
  });
  if (id === estado.trabalhoId) $("conversa-titulo").textContent = novo.trim();
  carregarTrabalhos();
}

/* Varias conversas para um grupo so, com uma pergunta. */
async function moverConversasParaGrupo(ids) {
  if (!ids.length) return;
  const primeira = (estado.recentes || []).find((t) => t.id === ids[0]) || {};
  const novo = await perguntar({
    titulo: ids.length === 1 ? "Grupo da conversa" : "Grupo de " + plural(ids.length, "conversa"), contexto: "Assistente",
    campo: { rotulo: "Nome do grupo", valor: ids.length === 1 ? (primeira.grupo || "") : "", placeholder: "sem grupo", icone: "folder", sugestoes: gruposConhecidos, obrigatorio: false,
             dica: "Vazio tira as conversas do grupo. Um grupo novo nasce com o nome que você escrever." },
    confirmar: "Guardar",
  });
  if (novo === null) return;
  for (const id of ids) {
    await fetch("/api/trabalhos/" + id + "/grupo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ grupo: novo.trim() }) });
  }
  lcSel.escolhidos.clear();
  avisoCert(plural(ids.length, "conversa") + (novo.trim() ? " em “" + novo.trim() + "”" : " sem grupo"), { tom: "ok" });
  carregarTrabalhos();
}

function apagarConversasEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/trabalhos/" + id, {
    rotulo: "conversa", contexto: "Assistente", texto: ids.length === 1 ? "A conversa sai da lista." : "As conversas saem da lista.",
    depois: () => { lcSel.escolhidos.clear(); if (ids.includes(estado.trabalhoId)) $("nova").click(); else carregarTrabalhos(); },
  });
}

function ligarExemplos() {
  document.querySelectorAll(".exemplo").forEach((b) => {
    b.onclick = () => { $("pedido").value = b.textContent; enviar(); };
  });
}

$("pilula-organizar").onclick = () => {
  $("centro").innerHTML = "";
  organizarComecar();
};

