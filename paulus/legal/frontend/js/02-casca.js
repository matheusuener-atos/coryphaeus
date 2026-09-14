/* ------------------------------------------------------------- casca */
/*
   O menu abre ao passar o mouse no trilho e fecha ao sair dele - por cima do
   conteudo, sem empurrar nada. Esc fecha. Ctrl+K leva ao campo de pedido de
   qualquer tela; Ctrl+N abre uma conversa nova.
*/

/* ------------------------------------------------------------- a janela */
/*
   A moldura do Windows saiu (frameless). O que ela fazia passa a ser feito
   aqui: os tres botoes do canto, arrastar pelo alto da tela e redimensionar
   pelas bordas.

   Arrastar e redimensionar NAO sao feitos a mão. Cada gesto manda UMA
   mensagem ao Python, que diz ao Windows "o clique foi na barra de titulo" ou
   "foi na borda de baixo"; dali em diante quem move e quem redimensiona e o
   proprio sistema, com o encaixe nas laterais e a fluidez de sempre. A
   alternativa - mandar a coordenada a cada movimento do mouse - seria uma
   viagem ate o Python por pixel, e a janela arrastaria aos solavancos.
*/

/* Quem arrasta a janela e o proprio pywebview, pela classe
   `pywebview-drag-region` no cabecalho da tela - com `DIRECT_TARGET_ONLY`
   ligado, so o clique no espaco vazio dele conta, e nao o clique nos botoes
   que ele contem. Aqui fica so o duplo-clique, que maximiza. */
function podeArrastarDaqui(e) {
  return e.button === 0 && e.target && e.target.classList &&
    e.target.classList.contains("pywebview-drag-region");
}

function ligarJanelaPropria() {
  const api = (window.pywebview || {}).api;
  if (!api || !api.janela_borda) return;
  document.documentElement.classList.add("com-janela");
  $("botoes-janela").hidden = false;
  $("bordas-janela").hidden = false;

  $("janela-minimizar").onclick = () => api.janela_minimizar();
  $("janela-fechar").onclick = () => api.janela_fechar();
  $("janela-tamanho").onclick = () => api.janela_alternar_tamanho().then(marcarTamanhoDaJanela);

  $("bordas-janela").querySelectorAll("[data-borda]").forEach((borda) => {
    borda.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      api.janela_borda(borda.dataset.borda);
    });
  });

  document.addEventListener("dblclick", (e) => {
    if (!podeArrastarDaqui(e)) return;
    api.janela_alternar_tamanho().then(marcarTamanhoDaJanela);
  });
}

/* O icone do meio continua o mesmo quadrado nos dois estados, como no
   desenho: o glifo de "restaurar" (dois quadrados sobrepostos) nao esta na
   fonte embutida, e o que muda e o que o botao diz ao passar o mouse. */
function marcarTamanhoDaJanela(maximizada) {
  const botao = $("janela-tamanho");
  botao.title = maximizada ? "Restaurar" : "Maximizar";
  botao.setAttribute("aria-label", botao.title);
}

/* O aviso na barra de titulo. `opcoes.icone` (info por padrao), `girar` para
   o que ainda esta em curso, `tom: "erro"`, `acao: { rotulo, fazer }` para o
   link sublinhado e `dura` em ms - 0 deixa o aviso ate o proximo. A fonte
   embutida nao tem ampulheta: o que espera gira `sync`. */
function avisoNaJanela(texto, opcoes) {
  const o = opcoes || {};
  const faixa = $("faixa-janela");
  faixa.className = "faixa-janela pywebview-drag-region visivel" + (o.girar ? " girando" : "") + (o.tom === "erro" ? " erro" : "");
  faixa.innerHTML = ic(o.icone || (o.tom === "erro" ? "error" : "info"), 16) +
    '<span class="faixa-texto pywebview-drag-region"></span>' +
    (o.acao ? '<button type="button"></button>' : "");
  faixa.querySelector(".faixa-texto").textContent = texto;
  if (o.acao) {
    const botao = faixa.querySelector("button");
    botao.textContent = o.acao.rotulo;
    botao.onclick = () => { fecharAvisoNaJanela(); o.acao.fazer(); };
  }
  clearTimeout(faixa.relogio);
  if (o.dura !== 0) faixa.relogio = setTimeout(fecharAvisoNaJanela, o.dura || 6000);
}

function fecharAvisoNaJanela() {
  const faixa = $("faixa-janela");
  clearTimeout(faixa.relogio);
  faixa.classList.remove("visivel");
}

window.addEventListener("pywebviewready", ligarJanelaPropria);
if (window.pywebview) ligarJanelaPropria();

/* Os icones do trilho entram um a um, de cima para baixo. A ordem sai daqui
   e nao do CSS porque o CSS teria de contar filhos - e o trilho tem riscos de
   separacao no meio, que mudam a conta a cada destino que entra ou sai. */
function ordenarTrilho() {
  $("trilho").querySelectorAll(".trilho-item").forEach((item, i) => {
    item.style.setProperty("--ordem", String(i));
  });
}
ordenarTrilho();

function abrirFlutuante() { $("menu-flutuante").classList.add("aberto"); }
function fecharFlutuante() {
  $("menu-flutuante").classList.remove("aberto");
  fecharGavetas();
  fecharMenu();
}

$("trilho").addEventListener("mouseenter", abrirFlutuante);
/* Fecha quando o ponteiro esta fora do trilho e do menu. Nao e mouseleave
   porque o menu abre DEBAIXO do ponteiro sem receber mouseenter - um
   movimento rapido para o conteudo nunca geraria o mouseleave. */
document.addEventListener("mousemove", (e) => {
  if (!$("menu-flutuante").classList.contains("aberto")) return;
  /* As bordas de redimensionar da janela sem moldura ficam POR CIMA de tudo,
     inclusive dos seis pixels da esquerda do trilho. Sem contar com elas
     aqui, encostar o mouse na beirada fechava o menu. */
  if (e.target && e.target.closest && e.target.closest("#menu-flutuante, #trilho, #bordas-janela")) return;
  fecharFlutuante();
});

/* A gaveta ao lado do menu: as telas antigas que ainda nao tem lugar. */
function fecharGavetas() {
  $("gaveta-antigos").hidden = true;
}
function alternarGaveta(id) {
  const alvo = $(id);
  const abrir = alvo.hidden;
  fecharGavetas();
  alvo.hidden = !abrir;
}
$("ver-antigos").onclick = () => alternarGaveta("gaveta-antigos");

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") fecharFlutuante();
  if (!(e.ctrlKey || e.metaKey)) return;
  const tecla = e.key.toLowerCase();
  if (tecla === "k") {
    e.preventDefault();
    const busca = $("bib-termo");
    if (busca) { busca.focus(); busca.select(); return; }
    if ($("compositor").hidden) $("nova").click();
    $("pedido").focus();
  } else if (tecla === "n") {
    e.preventDefault();
    $("nova").click();
  } else if (tecla === "s" && $("cfg-tela")) {
    e.preventDefault();
    if (cfg.sujo) salvarConfig();
  } else if (tecla === "1" || tecla === "2" || tecla === "3") {
    e.preventDefault();
    abrirDestino({ 1: "conversa", 2: "calendario", 3: "biblioteca" }[tecla]);
  } else if (e.key === "Enter" && $("ap-todos")) {
    // Aprovar o que esta marcado na fila. So vale com a tela de Aprovacoes
    // aberta: aprovar por atalho a partir de outra tela seria decidir sem ver.
    e.preventDefault();
    aprovarMarcados();
  } else if (e.shiftKey && tecla === "f") {
    e.preventDefault();
    alternarFocoPorAtalho();
  } else if (e.shiftKey && tecla === "s") {
    e.preventDefault();
    assinarDocumentoAberto();
  }
});

$("voltar").onclick = () => $("nova").click();

/* O painel da direita: guarda-se a escolha, como o desenho pede. */
function lateralPreferida() {
  try { return localStorage.getItem("paulus.lateral") !== "0"; } catch (err) { return true; }
}

function mostrarLateral(aberta) {
  $("lateral").hidden = !aberta;
  /* Corpo e rodape carregam a MESMA grade: e o que impede a coluna da direita
     de passar por baixo da barra de pedido quando ela aparece. */
  $("conversa-corpo").classList.toggle("com-lateral", aberta);
  $("conversa-rodape").classList.toggle("com-lateral", aberta);
  $("alternar-lateral").hidden = !$("centro").classList.contains("prosa");
}

$("alternar-lateral").onclick = () => {
  const abrir = $("lateral").hidden;
  try { localStorage.setItem("paulus.lateral", abrir ? "1" : "0"); } catch (err) { /* sem memoria */ }
  mostrarLateral(abrir);
};

/* A tela passa da postura de inicio para a de conversa: a coluna do texto
   ganha a medida de prosa e o painel da direita entra. */
function entrarNaConversa() {
  $("centro").classList.add("prosa");
  $("conversa-col").classList.remove("tela-dupla", "tela-cheia");
  $("acoes-tela").innerHTML = "";
  $("nav-tela").innerHTML = "";
  $("exportar-conversa").hidden = false;
  mostrarLateral(lateralPreferida());
}

/* A conversa em texto, para levar para fora. E o que "Exportar" faz enquanto
   nao existe formato melhor. */
function exportarConversa() {
  const t = estado.trabalho;
  if (!t) return;
  const linhas = [t.titulo, ""];
  for (const m of t.mensagens) linhas.push((m.autor === "pessoa" ? "Você: " : "PAULUS: ") + m.texto, "");
  const blob = new Blob([linhas.join("\n")], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (t.titulo || "conversa").replace(/[\\/:*?"<>|]+/g, "-") + ".txt";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
$("exportar-conversa").onclick = exportarConversa;

/* Animacoes reduzidas (Configuracoes > Aparencia). A classe fica no <html>
   para valer sobre tudo, e a escolha tambem vai para o navegador: as
   preferencias chegam por rede, e ate elas chegarem a tela ja se moveu. */
function aplicarAnimacoes(reduzidas) {
  document.documentElement.classList.toggle("sem-animacao", Boolean(reduzidas));
  try { localStorage.setItem("paulus.animacoes", reduzidas ? "reduzidas" : "normais"); } catch (err) { /* sem memoria */ }
}

/* Quem usa, no avatar: a foto enviada em Configuracoes ou, sem foto, as
   iniciais do nome cadastrado la. */
async function carregarUsuario() {
  try {
    const d = await (await fetch("/api/preferencias")).json();
    const p = d.preferencias || d;
    const foto = (d.marca || {}).foto || {};
    aplicarAnimacoes(p.animacoes_reduzidas);
    const nome = String(p.nome || "").trim();
    const partes = nome ? nome.split(/\s+/) : [];
    // Sem nome cadastrado fica a sigla do produto, que e o que o HTML ja traz.
    const iniciais = nome
      ? (partes[0][0] + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase()
      : "PL";

    // A versao no endereco: sem ela, trocar a foto nao mudaria a tela, que
    // continuaria mostrando a imagem que ja tem em maos. E tirar a foto tem
    // de desfazer a imagem aqui, senao o circulo fica com um retrato quebrado.
    const desenho = foto.tem ? '<img src="/marca/foto.png?v=' + foto.versao + '" alt="">' : "";
    for (const id of ["avatar", "avatar-menu"]) {
      if (desenho) $(id).innerHTML = desenho;
      else $(id).textContent = iniciais;
    }

    if (!nome) return;
    $("avatar").title = nome;
    $("usuario-nome").textContent = nome;
    if (p.oab) $("usuario-papel").textContent = "OAB " + p.oab;
  } catch (err) { /* sem preferencias, fica a sigla do produto */ }
}

