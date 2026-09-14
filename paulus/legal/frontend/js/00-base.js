const $ = (id) => document.getElementById(id);

/* ---------------------------------------------------------------- tema */
/* A escolha ja foi aplicada no <head>; aqui so o rotulo e a troca. */

function aplicarTema(tema) {
  document.documentElement.dataset.tema = tema;
  const escuro = tema === "escuro";
  const icone = escuro ? "light_mode" : "dark_mode";
  const rotulo = escuro ? "Tema claro" : "Tema escuro";
  $("tema-icone").textContent = icone;
  $("tema").title = rotulo;
  $("tema-menu-icone").textContent = icone;
  $("tema-rotulo").textContent = rotulo;
  try { localStorage.setItem("paulus.tema", tema); } catch (err) { /* sem memoria, tudo bem */ }
}

aplicarTema(document.documentElement.dataset.tema || "claro");

function alternarTema() {
  aplicarTema(document.documentElement.dataset.tema === "escuro" ? "claro" : "escuro");
}
$("tema").onclick = alternarTema;
$("tema-menu").onclick = alternarTema;

function esc(t) {
  const d = document.createElement("div");
  d.textContent = t == null ? "" : String(t);
  return d.innerHTML;
}

/*
   O indicador de trabalho do desenho: um anel fino com o topo em vinho,
   girando. A funcao guarda o nome antigo (coroa) porque quatro telas a
   chamam; o desenho da coroa foi embora com a marca antiga.
*/
function coroa(px) {
  return '<span class="indicador" style="width:' + px + "px;height:" + px + 'px"><i></i></span>';
}

/* Um icone da Material Symbols: o nome vira o desenho pela ligadura. */
function ic(nome, px) {
  return '<span class="ic' + (px ? " ic-" + px : "") + '">' + nome + "</span>";
}

const estado = {
  trabalhoId: null,
  trabalho: null,
  ocupado: false,
  contratos: 0,
  // Os documentos de que esta conversa trata. Lista vazia = o acervo inteiro.
  escopo: [],
  foco: [],          // o documento que a conversa vinha lendo
  modoEscopo: "",    // foco | acervo | perguntar (ver definirFoco)
  abertos: [],
  recentes: [],
  modelo: "",
  trechos: 0,
  pasta: "",
};

