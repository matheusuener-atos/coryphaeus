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

/* ------------------------------------------------------------ os avisos */
/*
   TODO aviso do programa sai na faixa de baixo, na largura inteira da
   janela: icone, frase e, quando ha o que fazer, um link sublinhado.
   `avisoCert` (16-dialogos.js), que as telas chamam, desagua aqui.

   Ha dois tipos. O passageiro (`avisoNaJanela`) diz o que acabou de
   acontecer e some sozinho. O fixo (`avisoFixoNaJanela`) diz um estado que
   continua valendo - o vinculo esperando o responsavel - e volta a aparecer
   sempre que um passageiro termina.

   `opcoes`: `icone` (info por padrao), `girar` para o que ainda esta em
   curso, `tom: "erro"`, `acao: { rotulo, fazer }` e `dura` em ms - 0 deixa o
   aviso ate o proximo. A fonte embutida nao tem ampulheta: o que espera gira
   `sync`, e o estado fixo usa `schedule`.
*/
const faixaJanela = { base: null, passageiro: false, relogio: 0 };

/* So a opcao do programa desliga o movimento - ver 22-responsivo.css. */
function animacoesLigadas() {
  return !document.documentElement.classList.contains("sem-animacao");
}

function pintarFaixa(texto, o) {
  const faixa = $("faixa-janela");
  const jaVisivel = faixa.classList.contains("visivel");
  faixa.className = "faixa-janela visivel" + (o.girar ? " girando" : "");
  faixa.innerHTML = ic(o.icone || (o.tom === "erro" ? "error" : "info"), 16) +
    '<span class="faixa-texto"></span>' +
    (o.acao ? '<button type="button"></button>' : "");
  faixa.querySelector(".faixa-texto").textContent = texto;
  faixa.title = texto;
  if (o.acao) {
    const botao = faixa.querySelector("button");
    botao.textContent = o.acao.rotulo;
    botao.onclick = () => { fecharAvisoNaJanela(); o.acao.fazer(); };
  }
  /* Um aviso por cima de outro que ainda esta a vista: a transicao de
     aparecer nao roda (ja esta visivel), e a troca seria seca. */
  if (jaVisivel && animacoesLigadas()) {
    Array.from(faixa.children).forEach((filho) => filho.animate(
      [{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }],
      { duration: 360, easing: "cubic-bezier(.16,1,.3,1)" }));
  }
}

function avisoNaJanela(texto, opcoes) {
  const o = opcoes || {};
  pintarFaixa(texto, o);
  faixaJanela.passageiro = true;
  clearTimeout(faixaJanela.relogio);
  if (o.dura !== 0) {
    faixaJanela.relogio = setTimeout(fecharAvisoNaJanela, o.dura || (o.acao ? 8000 : (o.tom === "erro" ? 10000 : 6000)));
  }
}

function avisoFixoNaJanela(texto, opcoes) {
  faixaJanela.base = texto ? { texto: texto, opcoes: opcoes || {} } : null;
  if (faixaJanela.passageiro) return;
  if (faixaJanela.base) pintarFaixa(faixaJanela.base.texto, faixaJanela.base.opcoes);
  else $("faixa-janela").classList.remove("visivel");
}

function fecharAvisoNaJanela() {
  clearTimeout(faixaJanela.relogio);
  faixaJanela.passageiro = false;
  const base = faixaJanela.base;
  avisoFixoNaJanela(base && base.texto, base && base.opcoes);
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

/* A intencao antes do gesto. O menu nao abre no primeiro pixel em que o
   ponteiro toca o trilho - quem so passa por ele a caminho da borda da janela
   nao quer uma cortina correndo -, e nao fecha no primeiro pixel fora dele,
   que e o que fazia a barra piscar num movimento torto de volta. */
const MENU_ABRE_MS = 70;
const MENU_FECHA_MS = 140;
const menuIntencao = { abre: 0, fecha: 0 };

function esquecerIntencao() {
  clearTimeout(menuIntencao.abre);
  clearTimeout(menuIntencao.fecha);
  menuIntencao.abre = 0;
  menuIntencao.fecha = 0;
}
function abrirFlutuante() {
  esquecerIntencao();
  $("menu-flutuante").classList.add("aberto");
}
function fecharFlutuante() {
  esquecerIntencao();
  $("menu-flutuante").classList.remove("aberto");
  fecharGavetas();
  fecharMenu();
}

$("trilho").addEventListener("mouseenter", () => {
  clearTimeout(menuIntencao.fecha);
  menuIntencao.fecha = 0;
  if ($("menu-flutuante").classList.contains("aberto") || menuIntencao.abre) return;
  menuIntencao.abre = setTimeout(abrirFlutuante, MENU_ABRE_MS);
});
$("trilho").addEventListener("mouseleave", () => {
  if ($("menu-flutuante").classList.contains("aberto")) return;
  clearTimeout(menuIntencao.abre);
  menuIntencao.abre = 0;
});
/* Fecha quando o ponteiro esta fora do trilho e do menu. Nao e mouseleave
   porque o menu abre DEBAIXO do ponteiro sem receber mouseenter - um
   movimento rapido para o conteudo nunca geraria o mouseleave. */
document.addEventListener("mousemove", (e) => {
  if (!$("menu-flutuante").classList.contains("aberto")) return;
  /* As bordas de redimensionar da janela sem moldura ficam POR CIMA de tudo,
     inclusive dos seis pixels da esquerda do trilho. Sem contar com elas
     aqui, encostar o mouse na beirada fechava o menu. */
  if (e.target && e.target.closest && e.target.closest("#menu-flutuante, #trilho, #bordas-janela")) {
    clearTimeout(menuIntencao.fecha);
    menuIntencao.fecha = 0;
    return;
  }
  if (!menuIntencao.fecha) menuIntencao.fecha = setTimeout(fecharFlutuante, MENU_FECHA_MS);
});

/* ------------------------------------------------------- troca de tela */
/*
   Toda tela nova ENTRA: cabecalho, corpo e rodape sobem 10 px enquanto
   aparecem, nessa ordem, com 50 ms entre um e outro. A barra de titulo e o
   trilho nao se mexem - sao a moldura, e moldura que pisca parece janela
   recarregando.

   O que chega depois (a tela abre com "somando..." e o conteudo vem da rede
   meio segundo mais tarde) nao pode entrar seco no fim da animacao: nos
   primeiros instantes depois da troca, a primeira vez que o `#centro` muda
   ele esmaece para dentro. Passado esse tempo nao ha mais esmaecer - uma
   tela que redesenha a cada tecla digitada na busca ficaria piscando.

   Trocar de visao dentro da mesma tela (Financeiro > Lancamentos) nao roda
   a entrada inteira: so o esmaecer do conteudo.

   Web Animations, e nao classe com @keyframes: nao precisa forcar reflow
   para reiniciar, e cancelar a anterior e uma chamada.
*/
const CURVA_ENTRA = "cubic-bezier(.16,1,.3,1)";
const troca = { tela: null, quando: 0, conteudo: false };

function transicaoDeTela(chave) {
  const outraTela = chave !== troca.tela;
  troca.tela = chave;
  troca.quando = performance.now();
  troca.conteudo = true;
  if (!outraTela || !animacoesLigadas()) return;
  [["conversa-topo", 0], ["conversa-corpo", 50], ["conversa-rodape", 90]].forEach(([id, atraso]) => {
    const el = $(id);
    el.getAnimations().forEach((x) => x.cancel());
    el.animate(
      [{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }],
      { duration: 520, delay: atraso, easing: CURVA_ENTRA, fill: "backwards" });
  });
}

/* DO INICIO PARA A CONVERSA. A primeira pergunta nao troca de tela - a
   mesma tela muda de postura: a saudacao some, a caixa de pedido desce para
   o pe e vira uma linha, o cabecalho e a conversa aparecem. Sem animacao era
   um salto. Agora a caixa DESLIZA de onde estava ate onde ficou (mede-se a
   posicao antes e depois e anima-se a diferenca, que e o jeito de animar
   uma mudanca de layout sem refazer o layout a cada quadro), o cabecalho
   desce aparecendo e a conversa sobe aparecendo, um pouco depois.
   `medirInicio()` antes de mudar a postura; `animarInicioParaConversa()`
   logo depois. */
function medirInicio() {
  return $("conversa-col").classList.contains("vazia") ? $("cartao-campo").getBoundingClientRect() : null;
}

function animarInicioParaConversa(antes) {
  if (!antes || $("conversa-col").classList.contains("vazia")) return;
  // A troca de postura ja e esta animacao: o esmaecer do conteudo nao repete.
  troca.tela = "inicio:conversa";
  troca.conteudo = false;
  if (!animacoesLigadas()) return;
  const caixa = $("cartao-campo");
  const depois = caixa.getBoundingClientRect();
  const dx = (antes.left + antes.width / 2) - (depois.left + depois.width / 2);
  const dy = (antes.top + antes.height / 2) - (depois.top + depois.height / 2);
  caixa.animate(
    [{ transform: "translate(" + dx + "px, " + dy + "px)", opacity: 0.7 }, { transform: "none", opacity: 1 }],
    { duration: 620, easing: CURVA_ENTRA });
  $("conversa-topo").animate(
    [{ opacity: 0, transform: "translateY(-8px)" }, { opacity: 1, transform: "none" }],
    { duration: 460, delay: 140, easing: CURVA_ENTRA, fill: "backwards" });
  $("centro").animate(
    [{ opacity: 0, transform: "translateY(18px)" }, { opacity: 1, transform: "none" }],
    { duration: 520, delay: 200, easing: CURVA_ENTRA, fill: "backwards" });
}

new MutationObserver(() => {
  if (!troca.conteudo) return;
  const passou = performance.now() - troca.quando;
  if (passou > 2000) { troca.conteudo = false; return; }
  /* Durante a entrada o conteudo ja esta aparecendo junto. */
  if (passou < 360) return;
  troca.conteudo = false;
  if (!animacoesLigadas()) return;
  const centro = $("centro");
  centro.getAnimations().forEach((x) => x.cancel());
  centro.animate(
    [{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }],
    { duration: 340, easing: CURVA_ENTRA });
}).observe($("centro"), { childList: true });

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
  /* So o corpo ganha a coluna do painel: a caixa de pedido, no rodape, nao
     se mexe quando ele abre (ver 02-conversa.css). */
  $("conversa-corpo").classList.toggle("com-lateral", aberta);
  $("alternar-lateral").hidden = !$("centro").classList.contains("prosa") || editorNaConversaAberto();
}

$("alternar-lateral").onclick = () => {
  const abrir = $("lateral").hidden;
  try { localStorage.setItem("paulus.lateral", abrir ? "1" : "0"); } catch (err) { /* sem memoria */ }
  alternarLateralAnimada(abrir);
};

/* O botao do painel anima os dois lados. Esconder so com `hidden` fazia o
   painel sumir de uma vez e a conversa pular para o meio; a transicao do CSS
   nao ajudava, porque a grade trocava de uma coluna para duas e isso nao se
   interpola. Aqui a coluna do painel vai de 316 px a 0 (mesmo numero de
   colunas, entao anda), o painel esmaece junto, e so no fim ele e escondido.
   Abrir faz o caminho inverso. */
let animacaoDaLateral = null;
function alternarLateralAnimada(abrir) {
  const corpo = $("conversa-corpo");
  const lateral = $("lateral");
  if (animacaoDaLateral) { animacaoDaLateral.forEach((a) => a.cancel()); animacaoDaLateral = null; }
  if (!animacoesLigadas()) { mostrarLateral(abrir); return; }
  const cheia = "minmax(0px, 1fr) 316px";
  const vazia = "minmax(0px, 1fr) 0px";
  if (abrir) {
    mostrarLateral(true);
    const coluna = corpo.animate([{ gridTemplateColumns: vazia }, { gridTemplateColumns: cheia }],
      { duration: 460, easing: CURVA_ENTRA });
    coluna.onfinish = () => { animacaoDaLateral = null; };
    animacaoDaLateral = [coluna];
    return;
  }
  const coluna = corpo.animate([{ gridTemplateColumns: cheia }, { gridTemplateColumns: vazia }],
    { duration: 380, easing: "cubic-bezier(.55,0,.45,1)", fill: "forwards" });
  const painel = lateral.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateX(18px)" }],
    { duration: 240, easing: "ease-in", fill: "forwards" });
  animacaoDaLateral = [coluna, painel];
  coluna.onfinish = () => {
    mostrarLateral(false);
    coluna.cancel();
    painel.cancel();
    animacaoDaLateral = null;
  };
}

/* A tela passa da postura de inicio para a de conversa: a coluna do texto
   ganha a medida de prosa e o painel da direita entra. */
function entrarNaConversa() {
  $("centro").classList.add("prosa");
  $("conversa-titulo").classList.add("renomeavel");
  $("conversa-titulo").title = "Clique para renomear";
  $("conversa-col").classList.remove("tela-dupla", "tela-cheia");
  $("acoes-tela").innerHTML = "";
  $("nav-tela").innerHTML = "";
  $("exportar-conversa").hidden = false;
  mostrarLateral(lateralPreferida() && !editorNaConversaAberto());
}

/* EXPORTAR A CONVERSA, em Markdown (padrao), texto ou Word.

   Na janela do programa o download do navegador nao funcionava - o link com
   `download` simplesmente nao levava a lugar nenhum. Ali a tela abre o
   "Salvar como" do Windows (com os tres tipos, Markdown primeiro) e o
   servidor grava o arquivo no caminho escolhido. No navegador, um menu com
   os tres formatos baixa o arquivo pelo servidor. */
async function exportarConversa() {
  const id = estado.trabalhoId;
  if (!id) return;
  const api = (window.pywebview || {}).api;
  const nome = (($("conversa-titulo").textContent || "conversa").replace(/[\\/:*?"<>|]+/g, "-").trim() || "conversa") + ".md";
  if (api && api.salvar_como) {
    const caminho = await api.salvar_como(nome);
    if (!caminho) return;
    const r = await fetch("/api/trabalhos/" + id + "/exportar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caminho: caminho }),
    });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    avisoCert("conversa exportada · " + d.nome, { tom: "ok" });
    return;
  }
  const baixar = (formato) => { location.href = "/api/trabalhos/" + id + "/exportar?formato=" + formato; };
  menuNaLinha($("exportar-conversa"), [
    { rotulo: "Markdown (.md)", icone: "description", acao: () => baixar("md") },
    { rotulo: "Texto (.txt)", icone: "notes", acao: () => baixar("txt") },
    { rotulo: "Word (.docx)", icone: "article", acao: () => baixar("docx") },
  ]);
}
$("exportar-conversa").onclick = (e) => { e.stopPropagation(); exportarConversa(); };

/* Animacoes reduzidas (Configuracoes > Aparencia). A classe fica no <html>
   para valer sobre tudo, e a escolha tambem vai para o navegador: as
   preferencias chegam por rede, e ate elas chegarem a tela ja se moveu. */
function aplicarAnimacoes(reduzidas) {
  document.documentElement.classList.toggle("sem-animacao", Boolean(reduzidas));
  try { localStorage.setItem("paulus.animacoes", reduzidas ? "reduzidas" : "normais"); } catch (err) { /* sem memoria */ }
}

/* As preferencias da pessoa que a casca usa na abertura. O avatar e o nome
   no pe da barra lateral sairam (pedido): a foto e o nome continuam em
   Configuracoes > Meus dados, onde sao editados. */
async function carregarUsuario() {
  try {
    const d = await (await fetch("/api/preferencias")).json();
    const p = d.preferencias || d;
    aplicarAnimacoes(p.animacoes_reduzidas);
  } catch (err) { /* sem preferencias, fica o padrao */ }
}

