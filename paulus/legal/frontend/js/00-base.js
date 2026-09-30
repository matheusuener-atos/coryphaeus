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
   O indicador de trabalho do desenho: um anel fino com o topo em destaque (neutro),
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

/* O icone da marca de um servico de fora (frontend/img/marcas): o botao que
   manda algo ao Google Drive, cria sala no Meet, sincroniza a Agenda ou
   mexe numa conta de e-mail leva a marca de quem recebe. Nomes:
   google-drive, google-meet, google-agenda, gmail, outlook, microsoft. */
function marca(nome, px) {
  const t = px || 16;
  return '<img class="marca-ic" src="/img/marcas/' + nome + '.svg" alt="" width="' + t + '" height="' + t + '">';
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
  // C1 (src/execucoes.py): a execucao cuja resposta esta pagina le, e o
  // "largou de proposito" (trocou de conversa; a resposta segue no servidor).
  execucaoId: "",
  saindo: false,
};

/* As chaves da conversa (docs/PROGRESSO-CONVERSA.md), lidas pela casca em
   /api/preferencias. Aqui, e nao no arquivo de cada etapa, porque o codigo
   que roda na abertura (antes dos arquivos seguintes) ja as consulta. */
function painelNovo() {
  return Boolean((window.PAULUS_CONVERSA || {}).painel);
}

function diagnostico() {
  return Boolean((window.PAULUS_CONVERSA || {}).diagnostico);
}

