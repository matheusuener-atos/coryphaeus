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

  menu.querySelector('[data-a="renomear"]').onclick = async () => {
    fecharMenu();
    const novo = await perguntar({ titulo: "Renomear conversa", contexto: "Assistente", campo: { rotulo: "Nome", valor: titulo, icone: "forum" }, confirmar: "Renomear" });
    if (!novo || !novo.trim()) return;
    await fetch("/api/trabalhos/" + id + "/renomear", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo: novo.trim() }),
    });
    if (id === estado.trabalhoId) $("conversa-titulo").textContent = novo.trim();
    carregarTrabalhos();
  };

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
    if (!(await confirmar({ titulo: "Apagar esta conversa?", contexto: "Assistente › " + titulo, texto: "A conversa sai da lista e do disco. Não dá para desfazer.", confirmar: "Apagar", perigo: true }))) return;
    await fetch("/api/trabalhos/" + id, { method: "DELETE" });
    if (id === estado.trabalhoId) $("nova").click();
    else carregarTrabalhos();
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
  $("conversa-col").classList.remove("tela-dupla", "tela-cheia", "com-lista");
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
  if (!(await confirmar({ titulo: "Apagar esta conversa?", contexto: "Assistente › " + $("conversa-titulo").textContent, texto: "A conversa sai da lista e do disco. Não dá para desfazer.", confirmar: "Apagar", perigo: true }))) return;
  await fetch("/api/trabalhos/" + estado.trabalhoId, { method: "DELETE" });
  $("nova").click();
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
    $("conversa-col").classList.remove("com-lista");
  }
}

/* Recentes: as ultimas conversas, no lugar dos exemplos de pergunta que o
   desenho nao tem. "Ver mais" abre a lista inteira aqui mesmo, embaixo. */
function desenharRecentes() {
  const alvo = $("recentes");
  const lista = (estado.recentes || []).slice(0, 3);
  if (!lista.length) { alvo.hidden = true; alvo.innerHTML = ""; return; }
  const aberta = $("conversa-col").classList.contains("com-lista");
  alvo.hidden = false;
  alvo.innerHTML = '<span class="rotulo-suave">Recentes</span>' +
    lista.map((t) =>
      '<button class="recente" data-abre="' + esc(t.id) + '">' + ic("forum", 16) +
      "<span>" + esc(t.titulo) + "</span></button>").join("") +
    '<button class="ver-mais" id="recentes-mais">' +
    (aberta ? "Recolher" + ic("chevron_left", 16) : "Ver mais" + ic("chevron_right", 16)) + "</button>";
  alvo.querySelectorAll("[data-abre]").forEach((b) => { b.onclick = () => abrirTrabalho(b.dataset.abre); });
  $("recentes-mais").onclick = () => alternarListaDeConversas(!aberta);
  if (aberta) desenharListaDeConversas();
}

/* A lista inteira, na propria tela: o bloco do pedido sobe e a tabela surge
   embaixo. O deslocamento e animado a partir da posicao medida antes e
   depois - a caixa vai para onde precisa ir, e o olho acompanha. */
function alternarListaDeConversas(abrir) {
  const bloco = $("cartao-campo");
  const antes = bloco.getBoundingClientRect().top;
  $("conversa-col").classList.toggle("com-lista", abrir);
  $("lista-conversas").hidden = !abrir;
  if (abrir) desenharListaDeConversas();
  desenharRecentes();
  const depois = bloco.getBoundingClientRect().top;
  const delta = antes - depois;
  const alvo = $("compositor").querySelector(".centro");
  if (delta && alvo) {
    alvo.style.transition = "none";
    alvo.style.transform = "translateY(" + delta + "px)";
    requestAnimationFrame(() => {
      alvo.style.transition = "transform .32s cubic-bezier(.2,.7,.3,1)";
      alvo.style.transform = "";
    });
  }
  if (abrir) {
    const busca = $("lc-busca");
    if (busca) busca.focus();
  }
}

const ESTADO_DA_CONVERSA = {
  executando: "trabalhando", aguardando: "esperando você", concluido: "concluída", pausado: "parada", falhou: "não deu",
};

function desenharListaDeConversas() {
  const caixa = $("lista-conversas");
  const termo = (caixa.dataset.termo || "").toLowerCase();
  const todas = estado.recentes || [];
  const lista = termo ? todas.filter((t) => (t.titulo || "").toLowerCase().includes(termo)) : todas;

  const linhas = lista.length ? lista.map((t) => {
    const andamento = t.estado === "aguardando"
      ? plural(t.pendencias || 1, "pedido") + " na fila"
      : (t.progresso !== null && t.progresso !== undefined && t.aberto ? t.progresso + "%" : "");
    return '<div class="tabela-linha colunas-conversas" data-id="' + esc(t.id) + '" data-titulo="' + esc(t.titulo) +
      '" data-grupo="' + esc(t.grupo || "") + '">' +
      '<span class="nome-doc"><span class="caixa-tipo">' + ic(t.tipo === "organizacao" ? "drive_file_move" : "forum", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(t.titulo) + "</b><small>" + esc(t.atualizado_em ? dataHoraCurta(t.atualizado_em) : "") + "</small></span></span>" +
      "<span>" + (t.grupo ? '<span class="etiqueta">' + esc(t.grupo) + "</span>" : '<span class="quando-doc">—</span>') + "</span>" +
      '<span class="estado-conversa"><i class="marca ' + esc(t.estado) + '"></i>' + (ESTADO_DA_CONVERSA[t.estado] || esc(t.estado)) + "</span>" +
      '<span class="quando-doc">' + andamento + "</span>" +
      '<button class="mais-linha" data-lc-menu="1" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("") : '<p class="nota">' + (termo ? "Nenhuma conversa com esse nome." : "Nenhuma conversa ainda.") + "</p>";

  caixa.innerHTML = '<div class="tabela-cartao"><div class="tabela-barra">' +
    '<span class="nota-barra">' + plural(todas.length, "conversa") + "</span>" +
    '<span class="direita"><label class="busca-tela">' + ic("search", 18) +
    '<input type="text" id="lc-busca" placeholder="Buscar conversa…" value="' + esc(caixa.dataset.termo || "") + '"></label>' +
    '<button class="fantasma com-icone" id="lc-recolher">' + ic("chevron_left", 16) + "Recolher</button></span></div>" +
    '<div class="tabela-cabecalho colunas-conversas"><span>Conversa</span><span>Grupo</span><span>Estado</span><span>Andamento</span><span></span></div>' +
    '<div class="tabela-corpo">' + linhas + "</div>" +
    '<div class="tabela-rodape"><span>clique para abrir · ··· para renomear, mover ou apagar</span><span class="cresce"></span><span>nada saiu da máquina hoje</span></div></div>';

  caixa.querySelectorAll(".tabela-linha").forEach((linha) => {
    linha.onclick = () => abrirTrabalho(linha.dataset.id);
    linha.querySelector("[data-lc-menu]").onclick = (e) => { e.stopPropagation(); abrirMenu(linha); };
  });
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

function ligarExemplos() {
  document.querySelectorAll(".exemplo").forEach((b) => {
    b.onclick = () => { $("pedido").value = b.textContent; enviar(); };
  });
}

$("pilula-organizar").onclick = () => {
  $("centro").innerHTML = "";
  organizarComecar();
};

