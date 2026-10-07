/* ------------------------------------------------------------ celular */
/*
   O Paulus no celular (pacote "Paulus - Telas Mobile", 02/10/2026; o CSS em
   css/52-celular.css). Ate 600 px a tela inicial e a do desenho `Assistente`:
   a marca d'agua no meio, os atalhos (Gravar reuniao, Digitalizar, Enviar
   arquivo, Conversas) e a caixa "Pergunte ao PAVLVS…" com "+ Fonte" e o
   microfone; a seta de enviar so quando ha texto. Embaixo, a barra de cinco
   icones: Assistente, Agenda e Acervo sao destinos de sempre (data-destino,
   js/08-destinos.js); Avisos abre o painel de avisos na tela inicial; Mais
   abre o perfil e a lista das Configuracoes (`Assistente - Mais`).

   O aviso do dia (`Assistente - Avisos`) vem numa faixa no alto, com a acao
   direta (a mesma do painel, com a pergunta antes) e o X, que guarda aquele
   aviso ate o fim do dia. Nada disto existe acima de 600 px.
*/

const cel = { maisAberto: false, perfil: null };
const CEL_LARGURA = window.matchMedia ? window.matchMedia("(max-width: 600px)") : null;

function celularNaTela() {
  return Boolean(CEL_LARGURA && CEL_LARGURA.matches);
}

/* ------------------------------------------------- a caixa de pedido */

const CEL_PLACEHOLDER = "Pergunte ao PAVLVS…";
const DESK_PLACEHOLDER = "Peça o que precisa dos seus documentos…";

function acertarCaixaDoCelular() {
  const pedido = $("pedido");
  const vazia = $("conversa-col").classList.contains("vazia");
  if (vazia) {
    const desejado = celularNaTela() ? CEL_PLACEHOLDER : DESK_PLACEHOLDER;
    if (pedido.placeholder === CEL_PLACEHOLDER || pedido.placeholder === DESK_PLACEHOLDER) pedido.placeholder = desejado;
  }
  $("cartao-campo").classList.toggle("tem-texto", Boolean(pedido.value.trim()));
}

/* ------------------------------------------------------- os atalhos */

async function atalhoDoCelular(qual, botao) {
  if (qual === "gravar") {
    // O mesmo pedido da conversa (`Conversa - Gravando`): a gravacao abre
    // na conversa, com a transcricao ao vivo.
    $("pedido").value = "Grave a reunião";
    acertarCaixaDoCelular();
    return enviar();
  }
  if (qual === "digitalizar") return $("cel-camera").click();
  if (qual === "enviar") return $("arquivos").click();
  if (qual === "conversas") {
    const abrir = $("lista-conversas").hidden;
    alternarListaDeConversas(abrir);
    botao.classList.toggle("ativo", abrir);
  }
}

/* ------------------------------------------- o aviso do dia no alto */

function celAvisoDispensado(id) {
  try { return localStorage.getItem("paulus.celular.aviso") === iso(new Date()) + "|" + id; } catch (err) { return false; }
}

/* O rotulo curto do desenho ("Pagar"): o botao da faixa tem 32 px. */
function rotuloCurtoDaAcao(x) {
  const r = (x && x.rotulo) || "";
  if (/recebid/i.test(r)) return "Receber";
  if (/pag/i.test(r)) return "Pagar";
  if (/conclu/i.test(r)) return "Concluir";
  if (/vist/i.test(r)) return "Visto";
  return r.split(" ")[0] || "Abrir";
}

function desenharAvisoDoCelular() {
  const caixa = $("cel-aviso");
  const botao = document.querySelector('.barra-celular [data-cel="avisos"] .cel-ponto');
  const lista = (typeof avs === "object" && avs.ligado && avs.avisos) || [];
  if (botao) botao.hidden = !lista.length;
  if (!caixa) return;
  const fila = lista.length ? filaDaFaixa(lista) : [];
  const a = fila[0];
  if (!a || avs.naInicio || celAvisoDispensado(a.id)) { caixa.hidden = true; caixa.innerHTML = ""; return; }
  const classeTom = tomDoAviso(a);
  const quando = String(a.quando || "");
  const mais = fila.length > 1 ? " · mais " + plural(fila.length - 1, "aviso") : "";
  const acao = ehConversaPelaMetade(a) ? { rotulo: "Continuar" } : (a.acoes || [])[0];
  const assinatura = a.id + "|" + fila.length + "|" + quando;
  if (caixa.dataset.assinatura === assinatura && !caixa.hidden) return;
  caixa.dataset.assinatura = assinatura;
  caixa.hidden = false;
  caixa.innerHTML = '<i class="' + classeTom + '"></i>' +
    '<div class="cel-aviso-texto"><b>' + esc(a.titulo) + "</b><span>" + esc(quando.charAt(0).toUpperCase() + quando.slice(1) + mais) + "</span></div>" +
    (acao ? '<button type="button" class="cel-aviso-acao">' + esc(ehConversaPelaMetade(a) ? "Continuar" : rotuloCurtoDaAcao(acao)) + "</button>" : "") +
    '<button type="button" class="cel-aviso-x" aria-label="Dispensar este aviso hoje">' + ic("close", 20) + "</button>";
  caixa.onclick = () => abrirAvisosNaInicio("");
  const b = caixa.querySelector(".cel-aviso-acao");
  if (b) b.onclick = (e) => { e.stopPropagation(); if (ehConversaPelaMetade(a)) abrirAviso(a); else fazerAcaoDoAviso(a, 0); };
  caixa.querySelector(".cel-aviso-x").onclick = (e) => {
    e.stopPropagation();
    try { localStorage.setItem("paulus.celular.aviso", iso(new Date()) + "|" + a.id); } catch (err) { /* so nesta janela */ }
    const fim = () => { caixa.hidden = true; caixa.innerHTML = ""; };
    if (animacoesLigadas()) sairDoAr(caixa, { aoFim: fim }); else fim();
  };
}

/* O modulo dos avisos redesenha quando a lista muda: a faixa vai junto. */
if (typeof desenharAvisos === "function") {
  const desenharAvisosAntes = desenharAvisos;
  // eslint-disable-next-line no-global-assign
  desenharAvisos = function () {
    desenharAvisosAntes();
    desenharAvisoDoCelular();
  };
}

/* ---------------------------------------------------------------- Mais */

const CEL_GRUPOS = [
  [["Meus dados", "config_perfil"], ["Escritório", "config_vinculos"], ["Acesso externo", "acesso"]],
  [["Assistente e modelo", "config_assistente"], ["Modelos", "config_modelos"], ["Módulos", "config_menu"],
    ["Conexões", "conexoes"], ["Desempenho", "desempenho"]],
  [["Biblioteca", "config_aprendizado"], ["Backup", "config_backup"], ["Lixeira", "config_lixeira"]],
  [["Plano e consumo", "consumo"], ["Notas fiscais", "notas"], ["Aparência", "config_aparencia"], ["Versão", "config_plano"]],
];

async function carregarPerfilDoCelular() {
  try {
    const r = await fetch("/api/preferencias");
    const d = r.ok ? await r.json() : null;
    const p = (d && d.preferencias) || {};
    const pessoa = p.pessoa || {};
    const escritorio = p.escritorio || {};
    const oab = String(pessoa.oab || "").trim();
    cel.perfil = {
      nome: String(pessoa.nome || "").trim(),
      linha: [oab ? (/^oab/i.test(oab) ? oab : "OAB " + oab) : "", String(escritorio.nome || "").trim()].filter(Boolean).join(" · "),
    };
  } catch (err) {
    cel.perfil = { nome: "", linha: "" };
  }
}

function htmlDoMais() {
  const p = cel.perfil || { nome: "", linha: "" };
  // Sem nome em Meus dados, o cabecalho diz onde por - nunca um nome de exemplo.
  const perfil = '<div class="cel-perfil"><b>' + esc(p.nome || "Seu nome") + "</b>" +
    "<span>" + esc(p.linha || (p.nome ? "" : "Preencha em Meus dados")) + "</span></div>";
  return '<div class="cel-mais-corpo">' + perfil + CEL_GRUPOS.map((g) => '<div class="cel-grupo">' +
    g.map(([rotulo, id]) => '<button type="button" data-cel-ir="' + id + '"><span>' + esc(rotulo) + "</span>" + ic("arrow_forward", 16) + "</button>").join("") +
    "</div>").join("") + "</div>";
}

async function abrirMaisCelular() {
  let caixa = $("cel-mais");
  if (!caixa) {
    caixa = document.createElement("div");
    caixa.id = "cel-mais";
    caixa.className = "cel-mais";
    caixa.setAttribute("role", "dialog");
    caixa.setAttribute("aria-label", "Mais");
    document.querySelector(".corpo").appendChild(caixa);
  }
  if (!cel.perfil) await carregarPerfilDoCelular();
  caixa.innerHTML = htmlDoMais();
  caixa.querySelectorAll("[data-cel-ir]").forEach((b) => {
    b.onclick = () => { fecharMaisCelular(); abrirTelaDaConversa(b.dataset.celIr); };
  });
  cel.maisAberto = true;
  requestAnimationFrame(() => caixa.classList.add("aberto"));
  marcarBarraDoCelular();
}

function fecharMaisCelular() {
  const caixa = $("cel-mais");
  cel.maisAberto = false;
  if (caixa) caixa.classList.remove("aberto");
  marcarBarraDoCelular();
}

/* ----------------------------------------------------------- a barra */

/* Assistente, Agenda e Acervo acendem pelo marcarDestino de sempre; Avisos
   e Mais, por aqui. Com o Mais aberto, so ele fica aceso. */
function marcarBarraDoCelular() {
  const barra = $("barra-celular");
  if (!barra) return;
  const avisos = typeof avs === "object" && avs.naInicio && $("conversa-col").classList.contains("vazia");
  barra.querySelector('[data-cel="mais"]').classList.toggle("ativo", cel.maisAberto);
  barra.querySelector('[data-cel="avisos"]').classList.toggle("ativo", !cel.maisAberto && Boolean(avisos));
  barra.classList.toggle("mais-aberto", cel.maisAberto);
  if (cel.maisAberto || avisos) {
    barra.querySelectorAll("[data-destino]").forEach((b) => b.classList.add("cel-apagado"));
  } else {
    barra.querySelectorAll("[data-destino]").forEach((b) => b.classList.remove("cel-apagado"));
  }
}

(function () {
  const barra = $("barra-celular");
  if (!barra) return;
  // Esmaecer curto entre as telas da barra (180-220 ms, ease-out).
  const trocar = () => {
    if (!animacoesLigadas()) return;
    const col = $("conversa-col");
    col.classList.remove("cel-trocando");
    void col.offsetWidth;
    col.classList.add("cel-trocando");
    setTimeout(() => col.classList.remove("cel-trocando"), 260);
  };
  barra.querySelectorAll("[data-destino]").forEach((b) => b.addEventListener("click", () => {
    if (cel.maisAberto) fecharMaisCelular();
    if (typeof avs === "object" && avs.naInicio && typeof fecharAvisosNaInicio === "function") fecharAvisosNaInicio();
    trocar();
    setTimeout(marcarBarraDoCelular, 0);
  }));
  barra.querySelector('[data-cel="avisos"]').onclick = () => {
    if (cel.maisAberto) fecharMaisCelular();
    trocar();
    abrirTelaDaConversa("avisos");
    setTimeout(marcarBarraDoCelular, 120);
  };
  barra.querySelector('[data-cel="mais"]').onclick = () => {
    if (cel.maisAberto) fecharMaisCelular(); else abrirMaisCelular();
  };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && cel.maisAberto) fecharMaisCelular(); });

  document.querySelectorAll("[data-cel-atalho]").forEach((b) => {
    b.onclick = () => atalhoDoCelular(b.dataset.celAtalho, b);
  });
  $("cel-fonte").onclick = () => abrirAnexar();
  $("cel-camera").onchange = (e) => {
    const lista = Array.from(e.target.files);
    e.target.value = "";
    if (lista.length) subirArquivos(lista);
  };
  $("pedido").addEventListener("input", acertarCaixaDoCelular);

  // A tela inicial aparece e some sem recarregar: a caixa, a faixa e a
  // barra acompanham.
  const col = $("conversa-col");
  if (typeof MutationObserver === "function") {
    new MutationObserver(() => {
      acertarCaixaDoCelular();
      desenharAvisoDoCelular();
      marcarBarraDoCelular();
      if (!$("lista-conversas").hidden) return;
      const conversas = document.querySelector('[data-cel-atalho="conversas"]');
      if (conversas) conversas.classList.remove("ativo");
    }).observe(col, { attributes: true, attributeFilter: ["class"] });
  }
  if (CEL_LARGURA && CEL_LARGURA.addEventListener) {
    CEL_LARGURA.addEventListener("change", () => { acertarCaixaDoCelular(); if (!celularNaTela()) fecharMaisCelular(); });
  }
  acertarCaixaDoCelular();
  desenharAvisoDoCelular();
})();
