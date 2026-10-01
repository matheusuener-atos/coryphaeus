/* ------------------------------------------------- a coluna da direita */
/*
   O pacote de telas de 01/10/2026 (docs/PLANO-TELAS-ASSISTENTE.md, T0): a
   coluna da direita da conversa TROCA DE PAPEL conforme a tarefa. Ela comeca
   como o contexto da resposta (progresso, trechos lidos, como respondi, onde
   procurei). Quando a conversa pede outra ferramenta, ela desliza ou se
   alarga ate a largura dessa ferramenta e mostra o conteudo dela:

     formulario    420 px  agenda, cadastros, lancamento, gravacao, financeiro
     configuracao  460 px  uma secao de Configuracoes aberta pelo chat
     ferramenta    o resto  documento, planilha, PDF, assinatura, agente;
                            a conversa fica com 560 px a esquerda

   Quando a operacao termina (salvar, assinar, enviar, cancelar, fechar), a
   coluna volta a ser a do contexto, com a mesma transicao. A largura mora em
   `--lado` (registrada em 00-tokens.css, anima sozinha); "Animacoes
   reduzidas" troca direto (html.sem-animacao, 30-movimento.css).

   Quem abre uma ferramenta chama abrirNoLado(papel, {chave, html, ligar,
   aoFechar}); quem termina chama voltarAoContexto(). O `aoFechar` e o
   gancho de quem abriu: roda quando a coluna volta ao contexto, ou quando
   outra ferramenta toma o lugar.
*/

const lado = {
  papel: "contexto",
  chave: "",
  aoFechar: null,
  // O contexto estava fechado quando a ferramenta abriu: ao terminar, a
  // coluna fecha em vez de voltar ao contexto.
  voltaFechado: false,
  saida: null,
};

const LADO_DURA_MS = 420;

function ladoAberto() {
  return !$("lateral").hidden && $("conversa-col").classList.contains("com-lado");
}

function papelDoLado() {
  return lado.papel;
}

/* A ferramenta ocupa o que sobra dos 560 px da conversa. Em px, medido: a
   porcentagem, dentro da coluna que anima, seria a largura dela mesma. */
function medirFerramenta() {
  const col = $("conversa-col");
  if (!col) return;
  col.style.setProperty("--largura-ferramenta", Math.max(320, col.clientWidth - 560) + "px");
}

if (window.ResizeObserver) new ResizeObserver(medirFerramenta).observe($("conversa-col"));

/* Muda sem animar: a troca de tela (abrirTela, nova conversa) ja esmaece o
   conteudo inteiro, e a coluna deslizando por cima disso era movimento em
   dobro. */
function semTransicaoDoLado(fazer) {
  const col = $("conversa-col");
  col.style.transition = "none";
  fazer();
  void col.offsetWidth;
  col.style.transition = "";
}

function marcarPapel(papel) {
  $("conversa-col").dataset.papel = papel;
  $("lateral").dataset.papel = papel;
}

/* O conteudo que sai esmaece; o que chega entra de 0 a 1, 8 px da direita. */
function trocarConteudoDoLado(sai, entra) {
  if (sai && sai !== entra && !sai.hidden) {
    if (animacoesLigadas()) {
      const a = sai.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 140, easing: "ease-in", fill: "forwards" });
      a.onfinish = () => { sai.hidden = true; a.cancel(); };
    } else {
      sai.hidden = true;
    }
  }
  if (!entra) return;
  entra.hidden = false;
  if (animacoesLigadas()) {
    entra.animate([{ opacity: 0, transform: "translateX(8px)" }, { opacity: 1, transform: "none" }],
      { duration: 280, delay: sai && sai !== entra ? 90 : 0, easing: CURVA_ENTRA, fill: "backwards" });
  }
}

/* Abre a coluna com uma ferramenta. Devolve o elemento onde ela mora. */
function abrirNoLado(papel, opcoes) {
  const o = opcoes || {};
  const col = $("conversa-col");
  const lat = $("lateral");
  const ferramenta = $("lado-ferramenta");
  const contexto = $("lado-contexto");
  const estavaAberto = ladoAberto();
  if (lado.papel === "contexto") lado.voltaFechado = !estavaAberto;

  // Outra ferramenta estava aberta: ela termina antes de dar o lugar.
  const anterior = lado.aoFechar;
  lado.aoFechar = null;
  if (anterior && lado.chave !== (o.chave || papel)) { try { anterior(); } catch (err) { /* quem fecha nao segura quem abre */ } }

  lado.papel = papel;
  lado.chave = o.chave || papel;
  lado.aoFechar = o.aoFechar || null;
  clearTimeout(lado.saida);

  if (papel === "contexto") {
    trocarConteudoDoLado(estavaAberto ? ferramenta : null, contexto);
    if (!estavaAberto) ferramenta.hidden = true;
  } else {
    if (o.html !== undefined) ferramenta.innerHTML = o.html;
    ferramenta.dataset.chave = lado.chave;
    trocarConteudoDoLado(estavaAberto ? contexto : null, ferramenta);
    if (!estavaAberto) contexto.hidden = true;
  }
  medirFerramenta();
  marcarPapel(papel);
  lat.hidden = false;
  if (!animacoesLigadas()) col.classList.add("com-lado");
  else {
    void lat.offsetWidth;
    col.classList.add("com-lado");
  }
  atualizarBotaoDoLado();
  if (o.ligar) o.ligar(ferramenta);
  return ferramenta;
}

/* A operacao terminou: a coluna volta a ser a do contexto - ou fecha, se o
   contexto estava fechado quando a ferramenta abriu. */
function voltarAoContexto(opcoes) {
  const o = opcoes || {};
  if (lado.papel === "contexto") return;
  const fim = lado.aoFechar;
  lado.aoFechar = null;
  lado.chave = "";
  const fechar = o.fechar !== undefined ? o.fechar : (lado.voltaFechado || !lateralPreferida());
  if (fechar) {
    fecharLado({ depois: () => {
      lado.papel = "contexto";
      marcarPapel("contexto");
      $("lado-ferramenta").hidden = true;
      $("lado-ferramenta").innerHTML = "";
      $("lado-contexto").hidden = false;
    } });
  } else {
    lado.papel = "contexto";
    trocarConteudoDoLado($("lado-ferramenta"), $("lado-contexto"));
    marcarPapel("contexto");
    setTimeout(() => { if (lado.papel === "contexto") $("lado-ferramenta").innerHTML = ""; }, LADO_DURA_MS);
  }
  atualizarBotaoDoLado();
  if (fim) { try { fim(); } catch (err) { /* o gancho de quem abriu */ } }
}

/* Fecha a coluna deslizando; so no fim ela some de verdade. */
function fecharLado(opcoes) {
  const o = opcoes || {};
  const col = $("conversa-col");
  const lat = $("lateral");
  clearTimeout(lado.saida);
  col.classList.remove("com-lado");
  const terminar = () => {
    if (col.classList.contains("com-lado")) return;
    lat.hidden = true;
    if (o.depois) o.depois();
    atualizarBotaoDoLado();
  };
  if (!animacoesLigadas() || lat.hidden) { terminar(); return; }
  lado.saida = setTimeout(terminar, 320);
}

/* O botao do cabecalho: mostra ou esconde o contexto. Com uma ferramenta de
   documento aberta ele sai (a ferramenta tem o proprio fechar). */
function atualizarBotaoDoLado() {
  const botao = $("alternar-lateral");
  if (!botao) return;
  const naConversa = $("conversa-col").classList.contains("em-conversa");
  botao.hidden = !naConversa || lado.papel === "ferramenta" || (typeof editorNaConversaAberto === "function" && editorNaConversaAberto());
  botao.classList.toggle("aberto", ladoAberto());
  $("exportar-conversa").classList.toggle("fora-do-lado", lado.papel === "ferramenta");
}

/* Fechar uma ferramenta de vez, sem animar (troca de tela, nova conversa). */
function largarFerramentaDoLado() {
  if (lado.papel === "contexto") return;
  const fim = lado.aoFechar;
  lado.aoFechar = null;
  lado.chave = "";
  lado.papel = "contexto";
  marcarPapel("contexto");
  $("lado-ferramenta").hidden = true;
  $("lado-ferramenta").innerHTML = "";
  $("lado-contexto").hidden = false;
  if (fim) { try { fim(); } catch (err) { /* o gancho de quem abriu */ } }
}

/* As partes do contexto recolhem pela cabeca: a seta gira e o corpo fecha
   como gaveta (abrirComoGaveta, js/03-assistente.js). */
document.addEventListener("click", (e) => {
  const cabeca = e.target.closest && e.target.closest("#lateral .lateral-cabeca");
  if (!cabeca) return;
  const corpo = cabeca.nextElementSibling;
  if (!corpo) return;
  const abrir = cabeca.getAttribute("aria-expanded") === "false";
  cabeca.setAttribute("aria-expanded", String(abrir));
  abrirComoGaveta(corpo, abrir);
});

marcarPapel("contexto");
