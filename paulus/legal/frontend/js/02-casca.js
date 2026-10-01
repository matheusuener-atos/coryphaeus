/* ------------------------------------------------------------- casca */
/*
   O menu abre ao passar o mouse no trilho e fecha ao sair dele - por cima do
   conteudo, sem empurrar nada. Esc fecha. Ctrl+K abre a busca de tudo
   (js/50-busca.js); Ctrl+N abre uma conversa nova.
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

/* A tela que nao avisa (as antigas, que desenham direto) continua ganhando a
   entrada pelo observador; quem chama entraConteudo() ja animou e some daqui
   pelo `troca.conteudo`. */
new MutationObserver(() => {
  if (!troca.conteudo) return;
  const passou = performance.now() - troca.quando;
  if (passou > 4000) { troca.conteudo = false; return; }
  const centro = $("centro");
  // O esqueleto de carregando nao conta: a entrada e do conteudo. Nem o
  // aviso curto de espera ("lendo…", "somando…"): o fade era gasto nele e o
  // conteudo de verdade chegava seco.
  if (centro.querySelector(".esqueleto")) return;
  const texto = centro.innerText.trim();
  if (texto.length < 80 && texto.endsWith("…")) return;
  troca.conteudo = false;
  entraConteudo(centro, { y: 6, duracao: 340 });
}).observe($("centro"), { childList: true, subtree: true });

/* ------------------------------------------------------- o movimento */
/*
   AS PECAS DE MOVIMENTO QUE TODA TELA USA (docs/ui/05). Ate aqui so a troca
   de tela animava - e animava cedo demais: a animacao rodava no esqueleto,
   porque a tela pede os dados e so depois desenha. Quem desenha agora diz
   "isto e conteudo novo" e a entrada acontece na hora certa.

   entraConteudo(el, o)    a entrada de um bloco (o.y, o.duracao, o.atraso)
   conteudoNovo(chave)     true quando o que vai na tela mudou de assunto
   abrirEmAltura(el)       o que a lista revela cresce em vez de saltar
   fecharEmAltura(el, fim) e encolhe antes de sair
   sairDoAr(el, o)         a saida de um pop-up ou de um popover
*/

function entraConteudo(el, opcoes) {
  const o = opcoes || {};
  // Quem anima por conta propria dispensa a entrada do observador.
  troca.conteudo = false;
  if (!el || !animacoesLigadas()) return;
  el.getAnimations().forEach((x) => x.cancel());
  el.animate(
    [{ opacity: 0, transform: "translateY(" + (o.y === undefined ? 8 : o.y) + "px)" }, { opacity: 1, transform: "none" }],
    { duration: o.duracao || 320, delay: o.atraso || 0, easing: CURVA_ENTRA, fill: "backwards" });
}

/* A tela se redesenha a cada clique (concluir, abrir uma linha): so vale
   animar quando o ASSUNTO muda - outra tela, outra visao, outro filtro. */
const assuntoNaTela = { chave: null };

function conteudoNovo(chave) {
  if (assuntoNaTela.chave === chave) return false;
  assuntoNaTela.chave = chave;
  return true;
}

/* A LISTA ENTRA LINHA A LINHA. Um atraso curto entre as primeiras faz a
   lista "montar" em vez de aparecer pronta; da decima em diante todas entram
   juntas, senao a espera vira lentidao. */
function entraLista(raiz, seletor) {
  if (!raiz || !animacoesLigadas()) return;
  const linhas = [...raiz.querySelectorAll(seletor)].slice(0, 24);
  linhas.forEach((linha, i) => {
    linha.animate(
      [{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }],
      { duration: 260, delay: Math.min(i, 9) * 26, easing: CURVA_ENTRA, fill: "backwards" });
  });
}

function abrirEmAltura(el) {
  if (!el || !animacoesLigadas()) return;
  const altura = el.scrollHeight;
  el.animate(
    [{ height: "0px", opacity: 0, transform: "translateY(-4px)" }, { height: altura + "px", opacity: 1, transform: "none" }],
    { duration: 260, easing: CURVA_ENTRA });
}

function fecharEmAltura(el, aoFim) {
  if (!el) { if (aoFim) aoFim(); return; }
  if (!animacoesLigadas()) { if (aoFim) aoFim(); return; }
  const animacao = el.animate(
    [{ height: el.scrollHeight + "px", opacity: 1 }, { height: "0px", opacity: 0 }],
    { duration: 180, easing: "cubic-bezier(.4,0,.6,1)" });
  animacao.onfinish = () => { if (aoFim) aoFim(); };
  animacao.oncancel = () => { if (aoFim) aoFim(); };
}

/* A saida: o pop-up e o popover somem andando, e nao no corte seco. `aoFim`
   e quem tira da tela de verdade. */
function sairDoAr(el, opcoes) {
  const o = opcoes || {};
  const fim = o.aoFim || (() => el.remove());
  if (!el || !animacoesLigadas()) { fim(); return; }
  const animacao = el.animate(
    [{ opacity: 1, transform: "none" }, { opacity: 0, transform: o.para || "translateY(6px) scale(.985)" }],
    { duration: o.duracao || 140, easing: "cubic-bezier(.4,0,1,1)" });
  animacao.onfinish = fim;
  animacao.oncancel = fim;
}

/* A PILULA DAS VISOES DESLIZA. Trocar de visao (Contribuir / Quem ja apoia,
   Mes / Semana / Tarefas...) redesenha a tela inteira, e a pilula saltava.
   Agora, no clique, guarda-se onde ela estava; quando a barra (a mesma, ou a
   redesenhada no mesmo lugar) mostra a nova ativa, uma pilula de passagem
   anda da antiga ate a nova. Nada muda no que cada tela faz. */
document.addEventListener("click", (e) => {
  const botao = e.target.closest && e.target.closest(".visoes > button");
  if (!botao || botao.classList.contains("ativa") || botao.disabled || !animacoesLigadas()) return;
  const barra = botao.parentElement;
  const antes = barra.querySelector(":scope > button.ativa");
  if (!antes) return;
  const lugar = barra.getBoundingClientRect();
  const de = antes.getBoundingClientRect();
  const inicio = performance.now();
  const procurar = () => {
    if (performance.now() - inicio > 900) return;
    const nova = [...document.querySelectorAll(".visoes")].find((v) => {
      const r = v.getBoundingClientRect();
      return Math.abs(r.top - lugar.top) < 3 && Math.abs(r.left - lugar.left) < 3;
    });
    const ativa = nova && nova.querySelector(":scope > button.ativa");
    const para = ativa && ativa.getBoundingClientRect();
    if (!para || (Math.abs(para.left - de.left) < 1 && Math.abs(para.width - de.width) < 1)) {
      requestAnimationFrame(procurar);
      return;
    }
    const caixa = nova.getBoundingClientRect();
    const pilula = document.createElement("span");
    pilula.className = "pilula-andando";
    Object.assign(pilula.style, {
      top: (para.top - caixa.top) + "px", left: (para.left - caixa.left) + "px",
      width: para.width + "px", height: para.height + "px",
    });
    nova.appendChild(pilula);
    nova.classList.add("deslizando");
    const anda = pilula.animate(
      [{ transform: "translateX(" + (de.left - para.left) + "px)", width: de.width + "px" },
        { transform: "none", width: para.width + "px" }],
      { duration: 300, easing: CURVA_ENTRA });
    const fim = () => { pilula.remove(); nova.classList.remove("deslizando"); };
    anda.onfinish = fim;
    anda.oncancel = fim;
  };
  requestAnimationFrame(procurar);
}, true);

/* O PAINEL AO LADO CHEGA DESLIZANDO. A ficha que abre a direita (Acervo,
   Servicos, Financeiro...) vem dentro do desenho da tela e aparecia de uma
   vez. Quando um painel surge onde nao havia, ele entra da direita; quando a
   tela se redesenha com o painel ja aberto, fica quieto. */
(() => {
  let havia = false;
  new MutationObserver(() => {
    const painel = $("centro").querySelector(".acervo-painel");
    const tem = Boolean(painel) && painel.getBoundingClientRect().width > 0;
    if (tem && !havia && animacoesLigadas()) {
      painel.animate([{ opacity: 0, transform: "translateX(18px)" }, { opacity: 1, transform: "none" }],
        { duration: 340, easing: CURVA_ENTRA });
    }
    havia = tem;
  }).observe($("centro"), { childList: true, subtree: true });
})();

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
    if (typeof abrirBusca === "function") { if (bsc.aberta) fecharBusca(); else abrirBusca(); return; }
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
  } else if (e.key === "Enter" && $("ap-fila")) {
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
  // C3: no celular o painel vem fechado e abre como folha de baixo, pelo botao.
  if ((window.PAULUS_CONVERSA || {}).painel && window.matchMedia && window.matchMedia("(max-width: 600px)").matches) return false;
  try { return localStorage.getItem("paulus.lateral") !== "0"; } catch (err) { return true; }
}

/* Mostra ou esconde a coluna da direita na hora, sem deslizar (troca de
   tela, conversa reaberta). Esconder larga a ferramenta que estivesse nela:
   a coluna volta a ser a do contexto (js/02-lado.js). */
function mostrarLateral(aberta) {
  semTransicaoDoLado(() => {
    if (!aberta) largarFerramentaDoLado();
    $("lateral").hidden = !aberta;
    $("conversa-col").classList.toggle("com-lado", aberta);
  });
  atualizarBotaoDoLado();
}

$("alternar-lateral").onclick = () => {
  const abrir = !ladoAberto();
  try { localStorage.setItem("paulus.lateral", abrir ? "1" : "0"); } catch (err) { /* sem memoria */ }
  alternarLateralAnimada(abrir);
};

/* O botao do cabecalho anima: a coluna desliza da direita (ou para ela) e a
   conversa se ajusta no mesmo passo, porque as duas leem a mesma `--lado`.
   Fechar com uma ferramenta aberta fecha a ferramenta junto. */
function alternarLateralAnimada(abrir) {
  if (abrir) { abrirNoLado("contexto"); return; }
  if (lado.papel !== "contexto") { voltarAoContexto({ fechar: true }); return; }
  fecharLado();
}

/* A tela passa da postura de inicio para a de conversa: a coluna do texto
   ganha a medida de prosa e o painel da direita entra. */
function entrarNaConversa() {
  if (typeof apoio !== "undefined") apoio.naTela = false;
  $("centro").classList.add("prosa");
  $("conversa-col").classList.add("em-conversa");
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
    aplicarModulos(p.modulos);
    /* As ideias do umbrelOS ligadas nesta máquina (Fotografar documento). */
    window.PAULUS_UMBREL = p.umbrel || {};
    /* As chaves da conversa (docs/PROGRESSO-CONVERSA.md). */
    window.PAULUS_CONVERSA = p.conversa || {};
    /* F1: a fila do modelo à vista (docs/PROGRESSO-APARELHO.md). */
    window.PAULUS_APARELHO = p.aparelho || {};
    document.documentElement.classList.toggle("pensando", Boolean(window.PAULUS_CONVERSA.pensando));
    document.documentElement.classList.toggle("painel-novo", Boolean(window.PAULUS_CONVERSA.painel));
  } catch (err) { /* sem preferencias, fica o padrao */ }
}

