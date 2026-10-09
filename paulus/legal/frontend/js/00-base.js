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

/* A linha-botao (css/57-linha-botao.css). `icones`: HTML de cada icone, ou
   {html, classe} (classe "lb-mono", "lb-22"...); `fim`: {tipo: status|acao|meta, texto};
   `classe`: centro, duas, tom-cf...; `attrs`: o resto da tag (id, data-*, disabled).
   Titulo, sub e fim chegam ja escapados. */
function linhaBotao(o) {
  const tag = o.tag || "button";
  const icones = (o.icones || []).filter(Boolean).map((i) => typeof i === "string"
    ? '<span class="lb-ic">' + i + "</span>" : '<span class="lb-ic ' + (i.classe || "") + '">' + i.html + "</span>").join("");
  const fim = o.fim ? '<span class="lb-fim lb-' + o.fim.tipo + (o.fim.classe ? " " + o.fim.classe : "") + '">' + o.fim.texto + "</span>" : "";
  return "<" + tag + (tag === "button" ? ' type="button"' : "") + ' class="linha-botao' + (o.classe ? " " + o.classe : "") + '"' + (o.attrs || "") + ">" +
    (icones ? '<span class="lb-icones">' + icones + "</span>" : "") +
    '<span class="lb-texto"><b class="lb-titulo">' + o.titulo + "</b>" + (o.sub ? '<small class="lb-sub">' + o.sub + "</small>" : "") + "</span>" +
    fim + "</" + tag + ">";
}

/* O monograma de uma ou duas letras (16 px e 12 px). */
function monogramaLb(letras) {
  const l = String(letras || "").toUpperCase();
  return { html: esc(l), classe: "lb-mono" + (l.length > 1 ? " lb-duas-letras" : "") };
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

/* F1: a fila do modelo à vista e a pergunta que espera na conversa (chave
   aparelho.fila, js/58-fila.js). Aqui porque o envio da conversa a consulta. */
function filaLigada() {
  return Boolean((window.PAULUS_APARELHO || {}).fila);
}

