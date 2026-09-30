/* ------------------------------------------------------ a busca de tudo */
/*
   Ctrl+K, ou a lupa do trilho: uma caixa que procura em tudo, como a da
   Cloudflare. Tres grupos:

     - Ir para: as telas do menu e as secoes de Configuracoes;
     - Acoes: o que se faz de qualquer lugar (calcular prazo, fazer backup,
       nova conversa, publicacoes do DJEN...);
     - No escritorio: os dados que casam com o termo (clientes e equipe,
       servicos, documentos do Acervo, tarefas, gravacoes, lancamentos,
       publicacoes) - de /api/busca, que respeita as permissoes de quem esta
       de fora.

   Setas navegam, Enter abre, Esc fecha. Sem acento conta igual.
*/

const bsc = { aberta: false, itens: [], sel: 0, relogio: null, pedido: 0, dados: [] };

function semAcentoBsc(t) {
  return String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function localBsc() { return typeof acessoDeFora === "undefined" || acessoDeFora.local; }

/* Acoes e atalhos que nao sao telas. `sinonimos` ajuda a achar pelo que a
   pessoa escreveria. */
function acoesBsc() {
  const a = [
    { titulo: "Nova conversa", caminho: "Assistente", icone: "add", sinonimos: "perguntar chat pedido", fazer: () => $("nova").click() },
    { titulo: "Calcular prazo", caminho: "Agenda › To-do", icone: "schedule", descricao: "dias úteis, feriados e recesso",
      sinonimos: "prazo processual cpc intimacao vencimento", fazer: () => calcularPrazo() },
    { titulo: "Publicações do DJEN", caminho: "Agenda › To-do", icone: "gavel", descricao: "intimações pela OAB, todo dia", local: true,
      sinonimos: "diario oficial dje djen intimacao publicacoes oab", fazer: () => abrirPublicacoesBsc() },
    { titulo: "Feriados do escritório", caminho: "Agenda › To-do › Publicações", icone: "today", local: true,
      sinonimos: "feriado municipal suspensao prazo", fazer: () => editarFeriados() },
    { titulo: "Fazer backup", caminho: "Configurações › Backup", icone: "archive", local: true,
      sinonimos: "copia seguranca restaurar", fazer: () => mostrarConfig("backup") },
    { titulo: "Saúde do PAULUS", caminho: "Configurações › Desempenho", icone: "speed", local: true,
      sinonimos: "diagnostico erro memoria suporte", fazer: () => mostrarConfig("desempenho") },
    { titulo: "Entrar sem internet", caminho: "Configurações › Escritório e equipe", icone: "key", local: true,
      sinonimos: "offline codigo celular autenticador trava", fazer: () => mostrarConfig("vinculos") },
    { titulo: "Convidar para a equipe", caminho: "Cadastros › Equipe", icone: "person_add", local: true,
      sinonimos: "convite colaborador acesso", fazer: () => (typeof convidarDaEquipe === "function" ? convidarDaEquipe() : abrirDestino("cadastros")) },
    { titulo: "Perguntar ao PAULUS no Explorer", caminho: "Configurações › Aparência e avisos", icone: "folder_open", local: true,
      sinonimos: "botao direito windows explorer menu", fazer: () => mostrarConfig("aparencia") },
    { titulo: "Trazer pasta do Google Drive", caminho: "Acervo › Incluir pasta", marca: "google-drive", local: true,
      descricao: "uma cópia no Acervo, conferida a cada 15 minutos", sinonimos: "drive google nuvem pasta sincronizar copiar",
      fazer: () => adicionarPastaAoAcervo({ drive: true }) },
    { titulo: "Novo agente do escritório", caminho: "Agentes", icone: "school", local: true,
      sinonimos: "agente especialista skill revisor triagem instrucoes", fazer: () => mostrarAgentes().then(() => novoAgente()) },
    { titulo: "Alternar tema claro/escuro", caminho: "Aparência", icone: "dark_mode", sinonimos: "tema escuro claro", fazer: () => alternarTema() },
    { titulo: "Sair", caminho: "Servidor", icone: "logout", local: true, sinonimos: "travar bloquear sair conta", fazer: () => sairDoServidor() },
  ];
  // Cada pasta do Drive copiada para o Acervo: um atalho para ela.
  (typeof bib !== "undefined" ? bib.driveCopias || [] : []).forEach((c) => {
    a.push({ titulo: c.nome, caminho: "Acervo › Google Drive", marca: "google-drive", descricao: plural(c.arquivos || 0, "documento") + ", com as subpastas",
      sinonimos: "drive google nuvem pasta", fazer: () => verCopiaDoDrive(c.caminho) });
  });
  return a.filter((x) => !x.local || localBsc()).map((x) => Object.assign({ grupo: "Ações" }, x));
}

/* O icone de cada tela: o do trilho, quando ela esta la; senao, um desta
   lista - todos existem na fonte (o nome fora dela aparece como letras). */
const ICONE_DA_TELA_BSC = {
  conversa: "forum", servicos: "work", gravacoes: "mic", calendario: "calendar_month", foco: "self_improvement",
  biblioteca: "inventory_2", editor: "description", assinar: "draw", caixa: "mail", financeiro: "payments",
  cadastros: "contacts", aprovacoes: "verified", config: "settings", apoiar: "favorite", planilha: "grid_view",
  organizar: "drive_file_move", tarefas: "task_alt", agendamento: "schedule", certificado: "workspace_premium",
  relatorios: "bar_chart", habilidades: "auto_awesome", conexoes: "hub", desempenho: "speed", aprendizado: "lightbulb",
  documentos: "description", email: "mail", ajuda: "help", leis: "menu_book", manual: "menu_book",
};

function iconeDaTelaBsc(id) {
  const noTrilho = document.querySelector('.trilho [data-destino="' + id + '"] .ic');
  return (noTrilho && noTrilho.textContent.trim()) || ICONE_DA_TELA_BSC[id] || "arrow_forward";
}

function telasBsc() {
  const itens = [];
  const vistos = new Set();
  (typeof DESTINOS !== "undefined" ? DESTINOS : []).concat(Object.values(typeof NOVOS_DESTINOS !== "undefined" ? NOVOS_DESTINOS : {}))
    .forEach((d) => {
      if (!d || !d.id || vistos.has(d.id) || d.pronta === false) return;
      vistos.add(d.id);
      itens.push({ grupo: "Ir para", titulo: d.nome, caminho: "", descricao: d.resolve || "", icone: iconeDaTelaBsc(d.id),
        fazer: () => abrirDestino(d.id) });
    });
  (typeof CFG_SECOES !== "undefined" ? CFG_SECOES : []).forEach(([id, rotulo, texto]) => {
    if (!localBsc() && id !== "perfil") return;
    itens.push({ grupo: "Ir para", titulo: rotulo, caminho: "Configurações", descricao: texto || "", icone: "settings",
      fazer: () => mostrarConfig(id) });
  });
  return itens;
}

function pontuarBsc(item, palavras) {
  const titulo = semAcentoBsc(item.titulo);
  const tudo = semAcentoBsc([item.titulo, item.caminho, item.descricao, item.sinonimos].join(" "));
  if (!palavras.every((p) => tudo.includes(p))) return 0;
  const q = palavras.join(" ");
  return titulo.startsWith(q) ? 3 : titulo.includes(q) ? 2 : 1;
}

function abrirBusca() {
  if (bsc.aberta) return;
  bsc.aberta = true;
  bsc.sel = 0;
  bsc.dados = [];
  if (typeof carregarCopiasDoDrive === "function" && localBsc()) carregarCopiasDoDrive();
  const veu = document.createElement("div");
  veu.className = "bsc-veu";
  veu.id = "bsc-veu";
  veu.innerHTML = '<div class="bsc-caixa" role="dialog" aria-label="Buscar em tudo">' +
    '<div class="bsc-topo">' + ic("search", 18) + '<input id="bsc-campo" type="text" placeholder="Buscar em tudo: telas, ações, clientes, serviços, documentos…" autocomplete="off" spellcheck="false">' +
    '<kbd class="bsc-esc">Esc</kbd></div><div class="bsc-lista" id="bsc-lista"></div>' +
    '<div class="bsc-pe"><span><kbd>↑</kbd><kbd>↓</kbd> para navegar</span><span><kbd>↵</kbd> para abrir</span></div></div>';
  document.body.appendChild(veu);
  requestAnimationFrame(() => veu.classList.add("aberta"));
  veu.addEventListener("mousedown", (e) => { if (e.target === veu) fecharBusca(); });
  const campo = document.getElementById("bsc-campo");
  campo.addEventListener("input", () => { bsc.sel = 0; desenharBusca(); pedirDadosBsc(campo.value); });
  campo.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); fecharBusca(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); bsc.sel = Math.min(bsc.itens.length - 1, bsc.sel + 1); desenharBusca(true); }
    else if (e.key === "ArrowUp") { e.preventDefault(); bsc.sel = Math.max(0, bsc.sel - 1); desenharBusca(true); }
    else if (e.key === "Enter") { e.preventDefault(); escolherBsc(bsc.sel); }
  });
  desenharBusca();
  campo.focus();
}

function fecharBusca() {
  bsc.aberta = false;
  clearTimeout(bsc.relogio);
  const v = document.getElementById("bsc-veu");
  if (!v) return;
  v.id = "";
  v.classList.remove("aberta");
  setTimeout(() => v.remove(), 160);
}

function pedirDadosBsc(texto) {
  clearTimeout(bsc.relogio);
  const q = String(texto || "").trim();
  if (q.length < 2) { bsc.dados = []; desenharBusca(); return; }
  const meu = ++bsc.pedido;
  bsc.relogio = setTimeout(async () => {
    let d = { itens: [] };
    try { d = await (await fetch("/api/busca?q=" + encodeURIComponent(q))).json(); } catch (err) { /* sem dados */ }
    if (meu !== bsc.pedido || !bsc.aberta) return;
    const ICONE = { cadastro: "contacts", servico: "work", documento: "description", tarefa: "task_alt", gravacao: "mic",
      lancamento: "payments", publicacao: "gavel" };
    bsc.dados = (d.itens || []).map((x) => Object.assign({ grupo: "No escritório", icone: ICONE[x.tipo] || "search", descricao: x.detalhe || "",
      fazer: () => abrirDadoBsc(x) }, x));
    desenharBusca();
  }, 180);
}

function desenharBusca(soSelecao) {
  const campo = document.getElementById("bsc-campo");
  const lista = document.getElementById("bsc-lista");
  if (!campo || !lista) return;
  const palavras = semAcentoBsc(campo.value).split(/\s+/).filter(Boolean);
  if (!soSelecao) {
    const fixos = telasBsc().concat(acoesBsc());
    const achados = palavras.length
      ? fixos.map((x) => [pontuarBsc(x, palavras), x]).filter(([p]) => p > 0).sort((a, b) => b[0] - a[0]).map(([, x]) => x)
      : acoesBsc().slice(0, 6);
    bsc.itens = achados.slice(0, 12).concat(palavras.length ? bsc.dados : []);
  }
  if (!bsc.itens.length) {
    lista.innerHTML = '<p class="bsc-vazio">' + (palavras.length ? "Nada com “" + esc(campo.value.trim()) + "”." : "") + "</p>";
    return;
  }
  let grupo = "";
  lista.innerHTML = bsc.itens.map((x, i) => {
    const cabeca = x.grupo !== grupo ? '<div class="bsc-grupo">' + esc((grupo = x.grupo) === "Ações" && !palavras.length ? "Ações rápidas" : x.grupo) + "</div>" : "";
    return cabeca + '<button type="button" class="bsc-item' + (i === bsc.sel ? " sel" : "") + '" data-bsc="' + i + '">' + (x.marca ? marca(x.marca, 18) : ic(x.icone || "arrow_forward", 18)) +
      '<span class="bsc-texto"><b>' + (x.caminho ? esc(x.caminho) + " › " : "") + esc(x.titulo) + "</b>" +
      (x.descricao ? '<span class="bsc-desc"> — ' + esc(x.descricao) + "</span>" : "") + "</span>" +
      (i === bsc.sel ? ic("arrow_forward", 16) : "") + "</button>";
  }).join("");
  lista.querySelectorAll("[data-bsc]").forEach((b) => {
    b.onclick = () => escolherBsc(Number(b.dataset.bsc));
    b.onmousemove = () => { if (bsc.sel !== Number(b.dataset.bsc)) { bsc.sel = Number(b.dataset.bsc); desenharBusca(true); } };
  });
  const sel = lista.querySelector(".bsc-item.sel");
  if (sel) sel.scrollIntoView({ block: "nearest" });
}

function escolherBsc(i) {
  const x = bsc.itens[i];
  if (!x) return;
  fecharBusca();
  try { x.fazer(); } catch (err) { avisoCert("não consegui abrir: " + err.message, { tom: "erro" }); }
}

function abrirPublicacoesBsc(id) {
  ag.tar.filtro = "publicacoes";
  ag.tar.lista = "";
  if (typeof pub !== "undefined") pub.aberta = id || null;
  marcarDestino("calendario");
  mostrarAgenda("tarefas");
}

async function abrirDadoBsc(x) {
  if (x.tipo === "cadastro") {
    const visao = x.cadastro_tipo === "cliente" ? "clientes" : x.cadastro_tipo === "despesa" ? "despesas" : "equipe";
    marcarDestino("cadastros");
    await mostrarCadastros(visao);
    if (typeof verFicha === "function") verFicha(x.id);
  } else if (x.tipo === "servico") {
    sv.aberto = { id: x.id };
    marcarDestino("servicos");
    mostrarServicos("trabalho");
  } else if (x.tipo === "documento") {
    verNoAcervo(x.titulo);
  } else if (x.tipo === "tarefa") {
    marcarDestino("calendario");
    abrirTarefaNaAgenda(x.id, x.prazo, x.concluida);
  } else if (x.tipo === "gravacao") {
    marcarDestino("gravacoes");
    abrirGravacao(x.id);
  } else if (x.tipo === "lancamento") {
    abrirDestino("financeiro");
  } else if (x.tipo === "publicacao") {
    abrirPublicacoesBsc(x.id);
  }
}

(function () {
  const b = document.getElementById("buscar-tudo");
  if (b) b.onclick = (e) => { e.stopPropagation(); abrirBusca(); };
  const m = document.getElementById("buscar-tudo-menu");
  if (m) m.onclick = (e) => { e.stopPropagation(); abrirBusca(); };
})();
