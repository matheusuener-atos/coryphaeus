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

  /* "Mover para grupo" abre, ao lado, os grupos que ja existem - um clique
     move. So "Novo grupo…" pergunta um nome. Passar o mouse abre; clicar
     tambem (para quem usa o teclado ou toca na tela). */
  const botaoGrupo = menu.querySelector('[data-a="grupo"]');
  const abrirGrupos = () => {
    if (menu.querySelector(".menu-sub")) return;
    const sub = document.createElement("div");
    sub.className = "menu-conversa menu-sub";
    sub.style.top = (botaoGrupo.offsetTop - 6) + "px";
    sub.innerHTML = itensDeGrupo(grupoAtual);
    menu.appendChild(sub);
    ligarItensDeGrupo(sub, [id], grupoAtual, () => fecharMenu());
  };
  botaoGrupo.onclick = abrirGrupos;
  botaoGrupo.onmouseenter = abrirGrupos;
  menu.querySelectorAll('[data-a]:not([data-a="grupo"])').forEach((b) => {
    b.addEventListener("mouseenter", () => { const sub = menu.querySelector(".menu-sub"); if (sub) sub.remove(); });
  });

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
  transicaoDeTela("conversa:" + id);
  $("compositor").hidden = false;
  estado.trabalho = await r.json();
  estado.trabalhoId = id;
  desenharTrabalho();
  carregarTrabalhos();
}

/* O INICIO LEMBRA COMO FICOU. Sair para outra tela e voltar devolve o
   inicio do jeito que estava: a lista de "Ver mais" aberta ou fechada, a
   visao (Conversas ou Grupos), a pasta em que se estava, a busca e a altura
   da rolagem. So na memoria desta sessao - abrir o programa de novo comeca
   do inicio limpo, como o usuario pediu. */
const lembrancaDoInicio = { lista: false, rolagem: 0 };

$("compositor").addEventListener("scroll", () => {
  if ($("conversa-col").classList.contains("vazia")) lembrancaDoInicio.rolagem = $("compositor").scrollTop;
}, { passive: true });

$("nova").onclick = () => {
  transicaoDeTela("inicio");
  estado.trabalhoId = null;
  estado.trabalho = null;
  definirEscopo([]);
  $("compositor").hidden = false;
  $("conversa-titulo").textContent = "Nova conversa";
  $("conversa-titulo").classList.remove("renomeavel");
  $("conversa-titulo").removeAttribute("title");
  $("apagar").hidden = true;
  $("exportar-conversa").hidden = true;
  $("centro").innerHTML = exemplos();
  $("centro").classList.remove("prosa");
  $("conversa-col").classList.remove("tela-dupla", "tela-cheia");
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
  /* A primeira pergunta tira a tela do inicio sem trocar de tela; voltar ao
     inicio depois disso e uma troca, e tem de animar. */
  if (temConversa && troca.tela === "inicio") troca.tela = "inicio:conversa";
  $("pedido").placeholder = temConversa
    ? "Pergunte outra coisa ou aponte outra pasta…"
    : "Peça o que precisa dos seus documentos…";
  if (!temConversa) {
    atualizarSaudacao();
    $("lista-conversas").hidden = !lembrancaDoInicio.lista;
    desenharRecentes();
    carregarAgora();
    $("registro").hidden = true;
    const rolagem = lembrancaDoInicio.rolagem;
    requestAnimationFrame(() => { $("compositor").scrollTop = rolagem; });
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
  /* Com a lista aberta, "Ver mais" sai: o botao de recolher ja esta na barra
     da propria lista, e dois botoes para a mesma coisa, um em cima do outro,
     so confundem. Ele volta quando a lista recolhe. */
  alvo.innerHTML = '<span class="rotulo-suave">Conversas recentes</span>' +
    lista.map((t) =>
      '<button class="recente" data-abre="' + esc(t.id) + '">' + ic("forum", 15) +
      "<span>" + esc(t.titulo) + "</span></button>").join("") +
    (aberta ? "" : '<button class="ver-mais" id="recentes-mais" title="Ver todas as conversas">Ver mais' + ic("chevron_right", 16) + "</button>");
  alvo.querySelectorAll("[data-abre]").forEach((b) => { b.onclick = () => abrirTrabalho(b.dataset.abre); });
  if (!aberta) $("recentes-mais").onclick = () => alternarListaDeConversas(true);
  if (aberta) desenharListaDeConversas();
}

/* A lista inteira, na propria tela, embaixo das recentes. Nada sobe nem se
   desloca: o inicio comeca no alto, e a lista so entra depois dele.

   Ela ABRE como gaveta, no ritmo do resto do programa: o cartao cresce de 0
   ate a altura dele (curva expo, .46 s) enquanto aparece, e as linhas chegam
   em cascata 6 px de baixo. "Ver mais" esmaece antes de sair. Recolher e o
   caminho de volta, mais curto (.3 s), e so no fim a lista some e "Ver mais"
   volta, esmaecendo para dentro. Web Animations, e nao transicao de CSS:
   `hidden` nao anima, e a altura de destino so se sabe depois de desenhar. */
const LISTA_ABRE_MS = 460;
const LISTA_FECHA_MS = 300;

function alternarListaDeConversas(abrir) {
  lembrancaDoInicio.lista = Boolean(abrir);
  const caixa = $("lista-conversas");
  if (caixa.recolhendo) { caixa.recolhendo.cancel(); caixa.recolhendo = null; caixa.style.overflow = ""; }
  const animar = animacoesLigadas();

  if (abrir) {
    const verMais = $("recentes-mais");
    caixa.hidden = false;
    desenharListaDeConversas();
    if (animar) {
      caixa.style.overflow = "hidden";
      const altura = caixa.scrollHeight;
      const margem = getComputedStyle(caixa).marginTop;
      caixa.animate(
        [{ height: "0px", marginTop: "0px", opacity: 0 }, { height: altura + "px", marginTop: margem, opacity: 1 }],
        { duration: LISTA_ABRE_MS, easing: CURVA_ENTRA }).onfinish = () => { caixa.style.overflow = ""; };
      caixa.querySelectorAll(".lc-linha").forEach((linha, i) => {
        if (i > 12) return;
        linha.animate(
          [{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }],
          { duration: 380, delay: 90 + i * 28, easing: CURVA_ENTRA, fill: "backwards" });
      });
    }
    if (verMais && animar) {
      verMais.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, easing: "ease", fill: "forwards" })
        .onfinish = () => desenharRecentes();
    } else {
      desenharRecentes();
    }
    const busca = $("lc-busca");
    if (busca) busca.focus({ preventScroll: true });
    return;
  }

  const fim = () => {
    caixa.hidden = true;
    caixa.style.overflow = "";
    desenharRecentes();
    const verMais = $("recentes-mais");
    if (verMais && animar) {
      verMais.animate([{ opacity: 0, transform: "translateX(-4px)" }, { opacity: 1, transform: "none" }],
        { duration: 320, easing: CURVA_ENTRA });
    }
  };
  if (!animar || caixa.hidden) { fim(); return; }
  caixa.style.overflow = "hidden";
  const anim = caixa.animate(
    [{ height: caixa.offsetHeight + "px", marginTop: getComputedStyle(caixa).marginTop, opacity: 1 },
     { height: "0px", marginTop: "0px", opacity: 0 }],
    { duration: LISTA_FECHA_MS, easing: "cubic-bezier(.55,0,.45,1)", fill: "forwards" });
  caixa.recolhendo = anim;
  anim.onfinish = () => { caixa.recolhendo = null; fim(); anim.cancel(); };
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

/* DUAS VISOES DA MESMA LISTA, alternadas na barra: CONVERSAS, todas numa
   lista so, cada uma com a etiqueta da pasta em que esta; e GRUPOS, em que
   cada grupo e uma pasta - com quantas conversas tem dentro - e as sem grupo
   ficam na pasta "Sem grupo". Clicar numa pasta entra nela, e o caminho
   "Grupos › Clientes" volta. Antes o grupo era so um nome apagado depois da
   hora, e passava despercebido. Buscar procura em tudo, nas duas visoes. A
   visao escolhida vale ate o programa fechar (ver `lembrancaDoInicio`). */
const SEM_GRUPO = "\u0000sem-grupo";
const lcNav = { visao: "conversas", grupo: "" };

function entrarNoGrupo(grupo) {
  lcNav.grupo = grupo;
  desenharListaDeConversas();
  animarLinhasDaLista(grupo ? 1 : -1);
}

function trocarVisaoDaLista(visao) {
  if (visao === lcNav.visao) return;
  lcNav.visao = visao;
  lcNav.grupo = "";
  desenharListaDeConversas();
  animarLinhasDaLista(visao === "grupos" ? 1 : -1);
}

/* Entrar e sair de pasta tem direcao: as linhas chegam da direita ao
   entrar e da esquerda ao voltar, no ritmo da gaveta da lista. */
function animarLinhasDaLista(direcao) {
  if (!animacoesLigadas()) return;
  $("lista-conversas").querySelectorAll(".lc-linha").forEach((linha, i) => {
    if (i > 12) return;
    linha.animate(
      [{ opacity: 0, transform: "translateX(" + (direcao * 12) + "px)" }, { opacity: 1, transform: "none" }],
      { duration: 380, delay: i * 24, easing: CURVA_ENTRA, fill: "backwards" });
  });
}

function desenharListaDeConversas() {
  const caixa = $("lista-conversas");
  const termo = (caixa.dataset.termo || "").toLowerCase();
  const todas = estado.recentes || [];
  const grupos = new Map();
  for (const t of todas) if (t.grupo) grupos.set(t.grupo, (grupos.get(t.grupo) || []).concat(t));
  const semGrupo = todas.filter((t) => !t.grupo);
  if (semGrupo.length) grupos.set(SEM_GRUPO, semGrupo);
  if (lcNav.grupo && !grupos.has(lcNav.grupo)) lcNav.grupo = "";
  const nomeDaPasta = (g) => (g === SEM_GRUPO ? "Sem grupo" : g);
  const totalDeGrupos = grupos.size - (semGrupo.length ? 1 : 0);
  let lista;
  let pastas = [];
  if (termo) lista = todas.filter((t) => (t.titulo || "").toLowerCase().includes(termo));
  else if (lcNav.visao === "conversas") lista = todas;
  else if (lcNav.grupo) lista = grupos.get(lcNav.grupo);
  else {
    lista = [];
    // "Sem grupo" por ultimo: e a sobra, e nao um grupo como os outros.
    pastas = [...grupos.keys()].filter((g) => g !== SEM_GRUPO).sort((a, b) => a.localeCompare(b, "pt-BR"));
    if (semGrupo.length) pastas.push(SEM_GRUPO);
  }
  for (const id of [...lcSel.escolhidos]) if (!todas.some((t) => t.id === id)) lcSel.escolhidos.delete(id);

  const linhasDePasta = pastas.map((g) => {
    const dentro = grupos.get(g);
    const andando = dentro.filter((t) => t.estado === "executando").length;
    return '<div class="lc-linha lc-pasta" data-pasta="' + esc(g) + '" role="button" tabindex="0">' +
      ic(g === SEM_GRUPO ? "folder_open" : "folder", 17) +
      '<span class="lc-nome"><b>' + esc(nomeDaPasta(g)) + "</b><small>" + plural(dentro.length, "conversa") + "</small></span>" +
      '<span class="estado-conversa">' + (andando ? '<span class="etiqueta ok anda">trabalhando</span>' : "") + "</span>" +
      (g === SEM_GRUPO ? '<span class="lc-mais-vazio"></span>'
        : '<button class="lc-mais" data-lc-menu-grupo="1" title="Mais" aria-label="Mais">' + ic("more_horiz", 17) + "</button>") +
      '<span class="lc-entrar">' + ic("chevron_right", 17) + "</span></div>";
  }).join("");

  /* A linha tem quatro coisas, e so quatro: o que e, o nome com a hora, como
     acabou e o menu. Na busca, a pasta de onde a conversa veio entra como
     etiqueta ao lado da hora. */
  const linhasDeConversa = lista.map((t) => {
    const quando = t.atualizado_em ? dataHoraCurta(t.atualizado_em) : "";
    const classe = "lc-linha" + (lcSel.escolhidos.has(t.id) ? " escolhida" : "");
    const pasta = t.grupo && (termo || lcNav.visao === "conversas") ? '<span class="lc-grupo">' + ic("folder", 13) + esc(t.grupo) + "</span>" : "";
    return '<div class="' + classe + '" data-id="' + esc(t.id) + '" data-sel="' + esc(t.id) + '" data-titulo="' + esc(t.titulo) +
      '" data-grupo="' + esc(t.grupo || "") + '">' +
      ic(t.tipo === "organizacao" ? "drive_file_move" : "forum", 17) +
      '<span class="lc-nome"><b>' + esc(t.titulo) + '</b><small class="lc-quando">' + esc(quando) + pasta + "</small></span>" +
      '<span class="estado-conversa"><span class="etiqueta ' + (TOM_DO_ESTADO[t.estado] || "") + '">' +
      (ESTADO_DA_CONVERSA[t.estado] || esc(t.estado)) + "</span></span>" +
      '<button class="lc-mais" data-lc-menu="1" title="Mais" aria-label="Mais">' + ic("more_horiz", 17) + "</button></div>";
  }).join("");

  const linhas = linhasDePasta + linhasDeConversa ||
    '<p class="lc-vazio">' + (termo ? "Nenhuma conversa com esse nome." : "Nenhuma conversa ainda.") + "</p>";

  const quantos = lcSel.escolhidos.size;
  const barra = quantos
    ? '<span class="lc-selecao">' + barraDeSelecao(quantos, true,
      '<span class="lc-mover"><button data-lc-grupo="1">' + ic("folder", 16) + "Mover para grupo" + ic("expand_more", 16) + "</button></span><span class=\"divisa-v\"></span>" +
      '<button class="botao-icone perigo" data-lc-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-lc-limpar", lista.length) + "</span>"
    : '<span class="lc-caminho">' +
      '<span class="visoes lc-visoes">' +
      '<button data-lc-visao="conversas"' + (lcNav.visao === "conversas" ? ' class="ativa"' : "") + ">Conversas <small>" + todas.length + "</small></button>" +
      '<button data-lc-visao="grupos"' + (lcNav.visao === "grupos" ? ' class="ativa"' : "") + ">Grupos <small>" + totalDeGrupos + "</small></button></span>" +
      (termo
        ? '<span class="lc-sep">·</span><small>' + plural(lista.length, "conversa") + " com “" + esc(caixa.dataset.termo) + "”</small>"
        : (lcNav.visao === "grupos" && lcNav.grupo
          ? '<button class="lc-migalha" data-lc-raiz="1">' + ic("chevron_left", 16) + "Grupos</button>" +
            '<span class="lc-sep">›</span><b>' + esc(nomeDaPasta(lcNav.grupo)) + "</b><small>" + plural(lista.length, "conversa") + "</small>"
          : "")) + "</span>";
  caixa.innerHTML = '<div class="lc-cartao"><div class="lc-barra">' + barra +
    '<label class="lc-busca">' + ic("search", 15) +
    '<input type="text" id="lc-busca" placeholder="Buscar conversa…" value="' + esc(caixa.dataset.termo || "") + '"></label>' +
    '<button class="lc-recolher" id="lc-recolher" title="Recolher" aria-label="Recolher">' + ic("view_sidebar", 16) + "</button></div>" +
    linhas + "</div>";

  caixa.querySelectorAll(".lc-linha[data-sel]").forEach((linha) => {
    linha.onclick = () => abrirTrabalho(linha.dataset.id);
    linha.querySelector("[data-lc-menu]").onclick = (e) => { e.stopPropagation(); abrirMenu(linha); };
  });
  caixa.querySelectorAll(".lc-pasta").forEach((linha) => {
    linha.onclick = () => entrarNoGrupo(linha.dataset.pasta);
    linha.onkeydown = (e) => {
      if (e.target !== linha) return;
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); entrarNoGrupo(linha.dataset.pasta); }
    };
    const mais = linha.querySelector("[data-lc-menu-grupo]");
    if (mais) {
      mais.onclick = (e) => {
        e.stopPropagation();
        const g = linha.dataset.pasta;
        menuNaLinha(mais, [
          { rotulo: "Renomear grupo", icone: "edit", acao: () => renomearGrupo(g) },
          "-",
          { rotulo: "Excluir grupo", icone: "delete", perigo: true, acao: () => excluirGrupo(g) },
        ]);
      };
    }
  });
  caixa.querySelectorAll("[data-lc-visao]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); trocarVisaoDaLista(b.dataset.lcVisao); };
  });
  const raiz = caixa.querySelector("[data-lc-raiz]");
  if (raiz) raiz.onclick = (e) => { e.stopPropagation(); entrarNoGrupo(""); };
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
  if (grupoSel) grupoSel.onclick = (e) => { e.stopPropagation(); moverConversasParaGrupo([...lcSel.escolhidos], grupoSel); };
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

/* O nome da conversa, no cabecalho, e o campo de renomear: clicar nele
   deixa escrever ali mesmo. Enter ou sair do campo guarda, Esc desiste. So
   vale com uma conversa aberta - nas outras telas o titulo e o nome da tela,
   e nao se renomeia "Financeiro". */
$("conversa-titulo").addEventListener("click", () => {
  const h = $("conversa-titulo");
  const id = estado.trabalhoId;
  if (!h.classList.contains("renomeavel") || h.isContentEditable || !id) return;
  const antes = h.textContent;
  h.contentEditable = "plaintext-only";
  h.classList.add("editando");
  h.focus();
  const faixa = document.createRange();
  faixa.selectNodeContents(h);
  const escolha = window.getSelection();
  escolha.removeAllRanges();
  escolha.addRange(faixa);

  let terminou = false;
  const terminar = async (guardar) => {
    if (terminou) return;
    terminou = true;
    h.removeEventListener("keydown", teclas);
    h.removeEventListener("blur", sair);
    h.contentEditable = "false";
    h.classList.remove("editando");
    h.scrollLeft = 0;
    const novo = h.textContent.replace(/\s+/g, " ").trim().slice(0, 80);
    if (!guardar || !novo || novo === antes) { h.textContent = antes; return; }
    h.textContent = novo;
    const r = await fetch("/api/trabalhos/" + id + "/renomear", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo: novo }),
    });
    if (!r.ok) {
      if (estado.trabalhoId === id) h.textContent = antes;
      avisoCert(await erroDe(r), { tom: "erro" });
      return;
    }
    if (estado.trabalho && estado.trabalho.id === id) estado.trabalho.titulo = novo;
    carregarTrabalhos();
  };
  const teclas = (e) => {
    if (e.key === "Enter") { e.preventDefault(); terminar(true); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); terminar(false); }
  };
  const sair = () => terminar(true);
  h.addEventListener("keydown", teclas);
  h.addEventListener("blur", sair);
});

/* Renomear um grupo leva todas as conversas dele junto. Com o nome de um
   grupo que ja existe, as duas pastas viram uma - o dialogo avisa. */
async function renomearGrupo(grupo) {
  const novo = await perguntar({
    titulo: "Renomear grupo", contexto: "Conversas › Grupos",
    campo: { rotulo: "Nome do grupo", valor: grupo, icone: "folder",
             dica: "Se já existir um grupo com esse nome, as conversas deste passam para ele." },
    confirmar: "Renomear",
  });
  if (novo === null || !novo.trim() || novo.trim() === grupo) return;
  const r = await fetch("/api/grupos/renomear", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ de: grupo, para: novo.trim() }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  if (lcNav.grupo === grupo) lcNav.grupo = d.para;
  avisoCert("grupo renomeado para “" + d.para + "”", { tom: "ok" });
  await carregarTrabalhos();
  desenharListaDeConversas();
}

/* Excluir o grupo NAO apaga conversa: elas vao para "Sem grupo". Desfazer
   devolve o nome so as conversas que sairam dele. */
async function excluirGrupo(grupo) {
  const dentro = (estado.recentes || []).filter((t) => t.grupo === grupo).length;
  if (!(await confirmar({
    titulo: "Excluir o grupo “" + grupo + "”?", contexto: "Conversas › Grupos",
    texto: "As " + plural(dentro, "conversa") + " dele não são apagadas: vão para “Sem grupo”.",
    confirmar: "Excluir grupo", perigo: true,
  }))) return;
  const r = await fetch("/api/grupos/renomear", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ de: grupo, para: "" }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  if (lcNav.grupo === grupo) lcNav.grupo = "";
  avisoCert("grupo “" + grupo + "” excluído · " + plural(d.ids.length, "conversa") + " em “Sem grupo”", {
    tom: "ok",
    acao: { rotulo: "Desfazer", fazer: async () => {
      for (const id of d.ids) {
        await fetch("/api/trabalhos/" + id + "/grupo", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ grupo: grupo }),
        });
      }
      avisoCert("grupo “" + grupo + "” de volta", { tom: "ok" });
      await carregarTrabalhos();
      desenharListaDeConversas();
    } },
  });
  await carregarTrabalhos();
  desenharListaDeConversas();
}

/* Varias conversas para um grupo so, com uma pergunta. */
/* A lista de destino de "Mover para grupo": os grupos que existem (o atual
   com o check), o divisor, e "Novo grupo…". "Tirar do grupo" so aparece
   para quem esta num. */
function itensDeGrupo(atual) {
  const nomes = gruposConhecidos || [];
  return nomes.map((g, i) =>
    '<button data-mover-grupo="' + i + '"' + (g === atual ? ' class="atual"' : "") + ">" +
    ic(g === atual ? "check" : "folder", 16) + '<span class="rotulo-botao">' + esc(g) + "</span></button>").join("") +
    (nomes.length ? '<div class="menu-risco"></div>' : "") +
    (atual ? '<button data-mover-sem="1">' + ic("folder_off", 16) + '<span class="rotulo-botao">Tirar do grupo</span></button>' : "") +
    '<button data-mover-novo="1">' + ic("create_new_folder", 16) + '<span class="rotulo-botao">Novo grupo…</span></button>';
}

function ligarItensDeGrupo(caixa, ids, atual, fechar) {
  const nomes = gruposConhecidos || [];
  caixa.querySelectorAll("[data-mover-grupo]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      fechar();
      const g = nomes[Number(b.dataset.moverGrupo)];
      if (g !== atual) moverConversasPara(ids, g);
    };
  });
  const sem = caixa.querySelector("[data-mover-sem]");
  if (sem) sem.onclick = (e) => { e.stopPropagation(); fechar(); moverConversasPara(ids, ""); };
  caixa.querySelector("[data-mover-novo]").onclick = async (e) => {
    e.stopPropagation();
    fechar();
    const novo = await perguntar({
      titulo: "Novo grupo", contexto: "Conversas › " + (ids.length === 1 ? "Mover para grupo" : "Mover " + plural(ids.length, "conversa")),
      campo: { rotulo: "Nome do grupo", placeholder: "ex.: Clientes", icone: "create_new_folder" },
      confirmar: "Criar e mover",
    });
    if (novo === null || !novo.trim()) return;
    moverConversasPara(ids, novo.trim());
  };
}

async function moverConversasPara(ids, grupo) {
  if (!ids.length) return;
  for (const id of ids) {
    await fetch("/api/trabalhos/" + id + "/grupo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ grupo: grupo }) });
  }
  lcSel.escolhidos.clear();
  avisoCert(plural(ids.length, "conversa") + (grupo ? " em “" + grupo + "”" : " sem grupo"), { tom: "ok" });
  await carregarTrabalhos();
  if (!$("lista-conversas").hidden) desenharListaDeConversas();
}

/* O botao "Mover para grupo" da barra de selecao abre a mesma lista, logo
   embaixo dele. */
function moverConversasParaGrupo(ids, botao) {
  if (!ids.length || !botao) return;
  fecharMenu();
  const caixa = botao.parentElement;
  const menu = document.createElement("div");
  menu.className = "menu-conversa menu-mover";
  menu.innerHTML = itensDeGrupo("");
  caixa.appendChild(menu);
  menu.onclick = (e) => e.stopPropagation();
  ligarItensDeGrupo(menu, ids, "", () => menu.remove());
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

