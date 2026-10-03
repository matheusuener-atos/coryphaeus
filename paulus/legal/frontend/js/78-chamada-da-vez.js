/* ------------------------------------------------- a vez dos avisos */
/*
   Na tela inicial, os avisos nao tem cartao nem botao proprio: o titulo da
   saudacao se reveza com eles. A saudacao entra, fica alguns segundos, da
   lugar ao assunto, volta - sempre com a caixa de pedido no lugar. No fim da
   frase de baixo, o que o clique faz ("Clique aqui para visualizar."); o
   clique no titulo ou na frase leva la.

     - avisos (js/53-avisos.js): "Você tem novos avisos." - o clique abre o
       painel no lugar da lista. Enquanto houver aviso, Aprovacoes pisca.

   Escrevendo na caixa, o revezamento para na saudacao. A frase de baixo usa
   o primeiro aviso da fila de verdade, nunca texto de exemplo.
*/

const vez = { assunto: "", fila: 0, relogio: 0 };
const VEZ_SAUDACAO_MS = 9000;
const VEZ_ASSUNTO_MS = 10000;
const VEZ_TROCA_MS = 700;

function assuntosDaVez() {
  if (!$("conversa-col").classList.contains("vazia") || avs.naInicio) return [];
  const lista = [];
  if (avs.ligado && (avs.avisos || []).length) lista.push("avisos");
  return lista;
}

function frasesDaVez() {
  const fila = filaDaFaixa(avs.avisos);
  const a = fila[0];
  const quando = a.quando ? " (" + a.quando + ")" : "";
  const resto = restoDaFaixa(fila, a);
  return [fila.length === 1 ? "Você tem um aviso novo." : "Você tem novos avisos.", "Clique aqui para visualizar.",
    a.titulo + quando + (resto ? ", " + resto : "") + "."];
}

/* Troca o que o bloco da saudacao mostra, com o esmaecer de sempre. */
function mostrarNaVez(assunto) {
  const bloco = document.querySelector(".saudacao-bloco");
  const titulo = $("chamada-vez"), sub = $("sub-vez");
  if (!bloco || !titulo) return;
  const aplicar = () => {
    vez.assunto = assunto;
    $("compositor").classList.toggle("na-vez", Boolean(assunto));
    bloco.dataset.vez = assunto;
    titulo.hidden = sub.hidden = !assunto;
    if (assunto) {
      const [t, dica, s] = frasesDaVez(assunto);
      titulo.textContent = t;
      titulo.title = dica.replace(/\.$/, "");
      sub.innerHTML = esc(s) + ' <span class="vez-dica">' + esc(dica) + "</span>";
    }
    // O texto novo ja esta no lugar, ainda apagado: so no quadro seguinte o
    // esmaecido sai, e ele aparece devagar (no mesmo quadro, surgiria de vez).
    void bloco.offsetWidth;
    requestAnimationFrame(() => requestAnimationFrame(() => bloco.classList.remove("vez-saindo")));
  };
  if (!animacoesLigadas() || vez.assunto === assunto) return aplicar();
  bloco.classList.add("vez-saindo");
  setTimeout(aplicar, VEZ_TROCA_MS);
}

/* O revezamento: saudacao, assunto, saudacao, proximo assunto... */
function passoDaVez() {
  clearTimeout(vez.relogio);
  const lista = assuntosDaVez();
  const escrevendo = ($("pedido").value || "").trim();
  if (!lista.length || escrevendo) {
    if (vez.assunto) mostrarNaVez("");
    vez.relogio = setTimeout(passoDaVez, VEZ_SAUDACAO_MS);
    return;
  }
  if (vez.assunto) {
    mostrarNaVez("");
    vez.relogio = setTimeout(passoDaVez, VEZ_SAUDACAO_MS);
  } else {
    mostrarNaVez(lista[vez.fila % lista.length]);
    vez.fila += 1;
    vez.relogio = setTimeout(passoDaVez, VEZ_ASSUNTO_MS);
  }
}

/* Chamada quando os avisos mudam: sem assunto valido, volta a
   saudacao na hora; o mesmo assunto tem a frase de baixo refeita. */
function atualizarChamadaDaVez() {
  const lista = assuntosDaVez();
  if (vez.assunto && !lista.includes(vez.assunto)) mostrarNaVez("");
  else if (vez.assunto && !document.querySelector(".saudacao-bloco.vez-saindo")) {
    const [, dica, frase] = frasesDaVez(vez.assunto);
    $("sub-vez").innerHTML = esc(frase) + ' <span class="vez-dica">' + esc(dica) + "</span>";
  }
}

(function () {
  const titulo = $("chamada-vez");
  if (!titulo) return;
  const irAoAssunto = () => {
    if (vez.assunto === "avisos") { abrirAvisosNaInicio(""); mostrarNaVez(""); }
  };
  titulo.onclick = irAoAssunto;
  $("sub-vez").onclick = irAoAssunto;
  $("pedido").addEventListener("input", () => { if (vez.assunto) passoDaVez(); });
  // Se a frase do banco nao vier (desligada, sem resposta), a saudacao
  // local aparece mesmo assim.
  setTimeout(revelarSaudacao, 2000);
})();

/* A abertura: a saudacao aparece uma vez so, ja com a frase final, e o
   revezamento comeca a contar dali - a saudacao fica uns segundos e os
   avisos, quando houver, entram. */
function revelarSaudacao() {
  if (vez.revelada) return;
  vez.revelada = true;
  const bloco = document.querySelector(".saudacao-bloco");
  if (bloco) requestAnimationFrame(() => requestAnimationFrame(() => bloco.classList.remove("abrindo")));
  clearTimeout(vez.relogio);
  vez.relogio = setTimeout(passoDaVez, 4000);
}
