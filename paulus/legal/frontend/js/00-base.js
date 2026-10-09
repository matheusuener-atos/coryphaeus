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

/* ------------------------------------- erro de campo e borda, nao texto */
/*
   Regra do dono (08/10/2026; css/58-campo-estado.css): o campo que nao fecha
   ganha a borda vinho; o que fecha, a verde. A frase do erro nao aparece na
   tela: fica num .so-leitor apontado por aria-describedby, com
   aria-invalid="true" no campo.

   marcarCampo(el, "erro" | "ok" | "", frase, caixa) marca um campo. A borda
   vai na `caixa` (ou na caixa em volta do input: .dialogo-caixa, .acesso-slug,
   .trava-casas), o aria no proprio input.

   vigiarCampo(el, conferir, o) liga a conferencia ao vivo. `conferir(valor)`
   devolve "" quando esta certo, a frase quando nao, ou null quando nao ha o
   que conferir (o campo fica neutro, sem verde). O campo so mostra estado
   depois de tocado: digitou e saiu, ou tentou enviar (conferirCampos). Ja
   vermelho, atualiza enquanto digita; verde que deixa de fechar no meio da
   digitacao volta a neutro, e so acusa ao sair. o.vazio: o que dizer do campo
   vazio (sem isso, vazio e neutro).

   conferirCampos(lista) marca todos como tocados, pinta e foca o primeiro
   que nao fecha; devolve true quando todos fecham. O botao de enviar nao
   trava por causa de campo vermelho: quem tenta ve a marca.
*/
function caixaDoCampo(el) {
  return (el && el.closest && el.closest(".dialogo-caixa, .acesso-slug, .trava-casas:not(.campo), .ec-senha, .fnc-para, .cert-senha-caixa")) || el;
}

let campoSrConta = 0;

function marcarCampo(el, estadoCampo, frase, caixa) {
  if (!el) return;
  const alvo = caixa || el._caixaCampo || caixaDoCampo(el);
  alvo.classList.toggle("campo-erro", estadoCampo === "erro");
  alvo.classList.toggle("campo-ok", estadoCampo === "ok");
  if (estadoCampo === "erro") el.setAttribute("aria-invalid", "true");
  else el.removeAttribute("aria-invalid");
  if (!el.dataset.srErro) {
    campoSrConta += 1;
    el.dataset.srErro = (el.id || "campo") + "-sr-" + campoSrConta;
  }
  const id = el.dataset.srErro;
  let sr = document.getElementById(id);
  const ligados = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter((x) => x && x !== id);
  if (estadoCampo === "erro" && frase) {
    if (!sr) {
      sr = document.createElement("span");
      sr.id = id;
      sr.className = "so-leitor";
      sr.setAttribute("aria-live", "polite");
      alvo.insertAdjacentElement("afterend", sr);
    }
    sr.textContent = maiusculaCampo(frase);
    ligados.push(id);
  } else if (sr) {
    sr.remove();
  }
  if (ligados.length) el.setAttribute("aria-describedby", ligados.join(" "));
  else el.removeAttribute("aria-describedby");
}

function maiusculaCampo(t) {
  const s = String(t || "");
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

/* O resultado da regra do campo, sem pintar: "" certo, frase, ou null (sem regra). */
function resultadoDoCampo(el) {
  const v = el.type === "checkbox" ? (el.checked ? "1" : "") : String(el.value || "");
  if (!v.trim() && el._campoVazio) return el._campoVazio;
  if (!v.trim()) return null;
  return el._conferirCampo ? el._conferirCampo(v) : null;
}

function pintarCampo(el) {
  const r = resultadoDoCampo(el);
  if (r === null || r === undefined) marcarCampo(el, "");
  else if (r) marcarCampo(el, "erro", r);
  else marcarCampo(el, "ok");
  return r || "";
}

function vigiarCampo(el, conferir, o) {
  if (!el) return el;
  const op = o || {};
  el._conferirCampo = conferir;
  el._campoVazio = op.vazio || "";
  if (op.caixa) el._caixaCampo = op.caixa;
  if (el._campoVigiado) return el;
  el._campoVigiado = true;
  el.addEventListener("blur", () => {
    if (String(el.value || "").trim() || el.dataset.campoTocado) { el.dataset.campoTocado = "1"; pintarCampo(el); }
  });
  el.addEventListener("input", () => {
    if (!el.dataset.campoTocado) return;
    const alvo = el._caixaCampo || caixaDoCampo(el);
    const r = resultadoDoCampo(el);
    // Vermelho atualiza ao vivo; o que nao era vermelho nao acusa no meio.
    if (r && !alvo.classList.contains("campo-erro")) marcarCampo(el, "");
    else pintarCampo(el);
  });
  return el;
}

/* Erro que veio do servidor e e de um campo: pinta de vermelho, sem texto. */
function campoErradoPeloServidor(el, frase) {
  if (!el) return;
  el.dataset.campoTocado = "1";
  marcarCampo(el, "erro", frase);
  // Campo sem regra vigiada: o vermelho sai quando a pessoa mexe nele.
  if (!el._campoVigiado) el.addEventListener("input", () => marcarCampo(el, ""), { once: true });
}

function conferirCampos(lista) {
  let primeiro = null;
  (lista || []).filter(Boolean).forEach((el) => {
    el.dataset.campoTocado = "1";
    if (pintarCampo(el) && !primeiro) primeiro = el;
  });
  if (primeiro) primeiro.focus();
  return !primeiro;
}

/* Regras de sempre, para quem vigia. */
const REGRA_CAMPO = {
  email: (v) => (/^[^\s@<>"]+@[^\s@<>"]+\.[a-z]{2,}$/i.test(String(v).trim()) ? "" : "confira o e-mail"),
  codigo6: (v) => (/^\d{6}$/.test(String(v).replace(/\s/g, "")) ? "" : "o código tem 6 números"),
  preenchido: (v) => (String(v).trim() ? "" : "preencha este campo"),
  senha10: (v) => (String(v).length < 10 ? "a senha precisa de pelo menos 10 caracteres" : ""),
};

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

