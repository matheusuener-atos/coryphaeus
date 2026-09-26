/* ------------------------------------------------- e-mail: transicoes */
/*
   As transicoes da tela E-mail inteira, num lugar so, por cima dos
   desenhos de js/18, 28, 29 e 31:

     trocar de visao, pasta, filtro ou busca   os blocos sobem e aparecem
                                               em sequencia, e as linhas
                                               da lista em cascata curta
     entrar e sair da selecao                  a barra de cima troca com
                                               um esmaecer
     trocar o texto da mensagem                original e formatado: o
                                               modulo esmaece; a traducao
                                               pronta entra em cascata,
                                               paragrafo por paragrafo

   Redesenho que nao muda nada disso (marcar uma linha, abrir mensagem) nao
   anima a tela: a mensagem aberta tem a animacao dela (27-email-caixa.css).
   Com "Animacoes reduzidas" ligado, nada disto roda.
*/

const EM_SOBE = [{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }];

function emAnimarTela(raiz) {
  const blocos = raiz.querySelectorAll(".ex-abre, .ex-lista, .em-principal > *, .em-pedir, .ec-palco > *, .ej-palco .cfg-cartao");
  blocos.forEach((el, i) => {
    el.animate(EM_SOBE, { duration: 360, delay: Math.min(i, 6) * 45, easing: CURVA_ENTRA, fill: "backwards" });
  });
  emAnimarLinhas(raiz, 140);
}

function emAnimarLinhas(raiz, atraso) {
  raiz.querySelectorAll(".ex-lista .tabela-corpo > .tabela-linha").forEach((linha, i) => {
    if (i > 14) return;
    linha.animate([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }],
      { duration: 280, delay: atraso + i * 18, easing: CURVA_ENTRA, fill: "backwards" });
  });
}

/* A traducao chega: cada paragrafo sobe e aparece, um atras do outro. */
function emCascata(itens) {
  if (!animacoesLigadas()) return;
  Array.from(itens).forEach((el, i) => {
    el.animate([{ opacity: 0, transform: "translateY(6px)", filter: "blur(2px)" }, { opacity: 1, transform: "none", filter: "none" }],
      { duration: 420, delay: Math.min(i, 10) * 70, easing: CURVA_ENTRA, fill: "backwards" });
  });
}

function emEsmaecer(el) {
  if (!el || !animacoesLigadas()) return;
  el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 220, easing: "ease-out" });
}

(function () {
  const desenharAntes = desenharEmail;
  let ultima = "";
  let selecionando = false;
  window.desenharEmail = function () {
    // Voltando de outra tela, o #email ainda nao existe: conta como troca.
    if (!document.getElementById("email")) ultima = "";
    const chave = [mail.visao, mail.pasta || "", mail.visao === "caixa" ? cx.visao : "", mail.busca || ""].join("|");
    const mudou = chave !== ultima;
    ultima = chave;
    const agoraSeleciona = cx.escolhidos.size > 0;
    const trocouSelecao = agoraSeleciona !== selecionando;
    selecionando = agoraSeleciona;
    const feito = desenharAntes.apply(this, arguments);
    const raiz = document.getElementById("email");
    if (raiz && animacoesLigadas()) {
      if (mudou) emAnimarTela(raiz);
      else if (trocouSelecao) emEsmaecer(raiz.querySelector(".ex-barra"));
    }
    return feito;
  };
})();
