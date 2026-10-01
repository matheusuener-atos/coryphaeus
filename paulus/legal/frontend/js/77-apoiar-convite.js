/* -------------------------------------------- o convite para apoiar */
/*
   Pacote de telas de 01/10/2026 (docs/PLANO-TELAS-ASSISTENTE.md):
   `Assistente - Apoiar` (o cartao "Apoie o PAULUS" na tela inicial) e
   `Conversa - Apoiar` (o mesmo cartao embaixo de uma resposta, "um pedido do
   PAULUS"). O pagamento e o de sempre (js/09-apoiar.js): Pix uma vez ou
   cartao todo mes, pelo Mercado Pago, com o recibo no e-mail.

   O que o cartao promete e o que e verdade aqui:
     - a frase de cima conta o que o PAULUS fez NESTE MES nesta maquina
       (GET /api/apoio/neste-mes); sem nada feito, o convite nao aparece;
     - a meta so aparece quando o site publica uma para o mes (o campo
       `meta` do mes em /api/publico/desenvolvimento); sem ela, a linha diz
       so o que entrou ate agora, e sem internet nem isso;
     - aparece no maximo uma vez por mes: "Agora nao" guarda o mes, e quem
       ja apoia (assinatura ativa ou Pix deste mes) nao ve o convite.
*/

const convite = { numeros: null, publico: null, carregadoEm: 0, pedindo: false, email: "" };
const CONVITE_VALORES = [[25, "um almoço"], [50, "mais escolhido"], [100, "escritório pequeno"]];
const CONVITE_RECARGA_MS = 10 * 60 * 1000;

function mesDoConvite() {
  return iso(new Date()).slice(0, 7);
}

function conviteDispensado() {
  try { return localStorage.getItem("paulus.apoio.convite") === mesDoConvite(); } catch (err) { return false; }
}

function dispensarConvite() {
  try { localStorage.setItem("paulus.apoio.convite", mesDoConvite()); } catch (err) { /* sem memoria: some so nesta janela */ }
  convite.dispensadoAgora = true;
}

/* Quem ja apoia nao e convidado: assinatura ativa, ou Pix pago neste mes. */
function jaApoiaEsteMes() {
  if (typeof lerApoioGuardado === "function") lerApoioGuardado();
  if (apoio.ativa) return true;
  const pago = String(apoio.pago || "");
  const m = pago.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  return Boolean(m && m[3] + "-" + m[2] === mesDoConvite());
}

async function carregarConvite(forcar) {
  if (convite.pedindo) return;
  if (!forcar && convite.carregadoEm && Date.now() - convite.carregadoEm < CONVITE_RECARGA_MS) return;
  convite.pedindo = true;
  try {
    const [numeros, publico, prefs] = await Promise.all([
      fetch("/api/apoio/neste-mes").then((r) => (r.ok ? r.json() : null)).catch(() => null),
      fetch("/api/publico/desenvolvimento").then((r) => (r.ok ? r.json() : null)).catch(() => null),
      fetch("/api/preferencias").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ]);
    convite.numeros = numeros;
    convite.publico = publico;
    convite.email = (prefs && prefs.preferencias && (prefs.preferencias.pessoa || {}).email) || "";
    convite.carregadoEm = Date.now();
  } finally {
    convite.pedindo = false;
  }
}

function conviteCabe() {
  const n = convite.numeros;
  return Boolean(n && (n.documentos || n.lancamentos) && !conviteDispensado() && !convite.dispensadoAgora && !jaApoiaEsteMes());
}

/* "Este mes, o PAULUS ja leu 4 documentos e montou 2 lancamentos para voce." */
function fraseDoConvite() {
  const n = convite.numeros || {};
  const partes = [];
  if (n.documentos) partes.push("já leu " + plural(n.documentos, "documento"));
  if (n.lancamentos) partes.push((partes.length ? "montou " : "já montou ") + plural(n.lancamentos, "lançamento"));
  return "Este mês, o PAULUS " + partes.join(" e ") + " para você.";
}

const MESES_DO_CONVITE = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

function metaDoConvite() {
  const mes = mesDoConvite();
  const nome = MESES_DO_CONVITE[Number(mes.slice(5, 7)) - 1];
  const dados = ((convite.publico || {}).meses || []).find((m) => m.month === mes);
  const faltam = (convite.numeros || {}).faltam_dias;
  const restam = faltam ? " · faltam " + plural(faltam, "dia") : "";
  if (!dados) return "";
  const c = dados.contributions || {};
  const total = Number(c.total || 0);
  const quantos = Number(c.count || 0);
  const apoiando = quantos ? plural(quantos, "apoio") + " em " + nome : "";
  if (dados.meta) {
    const pct = Math.min(100, Math.round((total / Number(dados.meta)) * 100));
    return '<div class="cv-meta"><div class="cv-meta-linha"><b>Meta de ' + esc(nome) + '</b><span class="vazio-flex"></span><span class="cv-num">' +
      esc(emReais(total * 100).replace(",00", "")) + " de " + esc(emReais(Number(dados.meta) * 100).replace(",00", "")) + "</span></div>" +
      '<div class="cv-barra"><i style="width:' + pct + '%"></i></div>' +
      '<span class="cv-sub">' + esc((apoiando || "nenhum apoio ainda") + restam) + "</span></div>";
  }
  if (!quantos) return "";
  return '<div class="cv-meta"><span class="cv-sub">Até agora, ' + esc(emReais(total * 100)) + " de " + esc(apoiando) + esc(restam) + "</span></div>";
}

function rotuloDoBotaoDoConvite() {
  const v = valorDoApoio();
  const texto = v ? emReais(Math.round(v * 100)).replace(",00", "") : "";
  if (!texto) return "Apoiar";
  return "Apoiar " + texto + (apoio.forma === "pix" ? "" : "/mês");
}

function cartaoDoConvite(onde) {
  if (typeof lerApoioGuardado === "function") lerApoioGuardado();
  const forma = (f, rotulo) => {
    const classe = "cv-forma-op" + (apoio.forma === f ? " ativa" : "");
    return '<button type="button" class="' + classe + '" data-cv-forma="' + f + '">' + rotulo + "</button>";
  };
  const valores = CONVITE_VALORES.map(([v, sub]) => {
    const classe = "cv-valor" + (apoio.valor === v ? " ativo" : "");
    return '<button type="button" class="' + classe + '" data-cv-valor="' + v + '"><b>R$ ' + v + "</b><span>" + esc(sub) + "</span></button>";
  }).join("");
  const outro = !apoio.valor && centavosDe(apoio.outro) > 0;
  const classeOutro = "cv-valor" + (outro ? " ativo" : "");
  const email = (apoio.email || convite.email || "").trim();
  return '<div class="cv-cartao" data-cv-onde="' + onde + '">' +
    '<div class="cv-esq"><div class="cv-titulo">' + ic("favorite", 18) + "<b>" + esc(fraseDoConvite()) + "</b></div>" +
    "<p>Ele roda na sua máquina, sem assinatura nem cobrança por uso. Quem usa e pode contribuir paga o desenvolvimento e mantém o programa livre para todos.</p>" +
    metaDoConvite() + "</div>" +
    '<div class="cv-dir"><div class="cv-forma">' + forma("pix", "Pix · uma vez") + forma("cartao", "Cartão · todo mês") + "</div>" +
    '<div class="cv-valores">' + valores + '<button type="button" class="' + classeOutro + '" data-cv-outro="1"><b>' +
    (outro ? esc(emReais(centavosDe(apoio.outro)).replace(",00", "")) : "Outro") + "</b><span>você define</span></button></div>" +
    '<div class="cv-pe"><span class="cv-recibo">pelo Mercado Pago' + (email ? " · recibo em " + esc(email) : "") + "</span>" +
    '<button type="button" class="cv-nao" data-cv-nao="1">Agora não</button>' +
    '<button type="button" class="cv-apoiar" data-cv-apoiar="1">' + ic("favorite", 15) + esc(rotuloDoBotaoDoConvite()) + "</button></div></div></div>";
}

function ligarConvite(raiz, aoMudar, aoSair) {
  raiz.querySelectorAll("[data-cv-forma]").forEach((b) => {
    b.onclick = () => { apoio.forma = b.dataset.cvForma; acertarRecorrencia(); guardarApoio(); aoMudar(); };
  });
  raiz.querySelectorAll("[data-cv-valor]").forEach((b) => {
    b.onclick = () => { apoio.valor = Number(b.dataset.cvValor); guardarApoio(); aoMudar(); };
  });
  const outro = raiz.querySelector("[data-cv-outro]");
  if (outro) outro.onclick = async () => {
    const r = await perguntar({ titulo: "Quanto você quer apoiar?", contexto: "Apoiar o projeto",
      campo: { rotulo: "Valor", valor: apoio.outro || "", placeholder: "100,00", sufixo: apoio.forma === "pix" ? "uma vez" : "por mês", icone: "payments" },
      confirmar: "Usar este valor" });
    const texto = r && typeof r === "object" ? r.valor : r;
    if (!texto) return;
    apoio.valor = 0;
    apoio.outro = String(texto);
    guardarApoio();
    aoMudar();
  };
  const nao = raiz.querySelector("[data-cv-nao]");
  if (nao) nao.onclick = () => { dispensarConvite(); aoSair(); };
  const apoiar = raiz.querySelector("[data-cv-apoiar]");
  if (apoiar) apoiar.onclick = async () => {
    if (!(apoio.email || "").trim()) {
      const sugerido = convite.email || "";
      const r = await perguntar({ titulo: "Para onde vai o recibo?", contexto: "Apoiar o projeto",
        campo: { rotulo: "E-mail", valor: sugerido, placeholder: "voce@escritorio.com.br", icone: "mail" }, confirmar: "Continuar" });
      const texto = r && typeof r === "object" ? r.valor : r;
      if (!texto) return;
      apoio.email = String(texto).trim();
      guardarApoio();
    }
    acertarRecorrencia();
    if (apoio.forma === "pix") await apoioPagarPix();
    else await apoioAssinar();
    aoMudar();
  };
}

/* ------------------------------------------------- na tela inicial */

async function desenharConviteNaInicio() {
  const caixa = $("ap-convite");
  if (!caixa) return;
  if (!$("conversa-col").classList.contains("vazia")) { caixa.hidden = true; return; }
  await carregarConvite(false);
  if (!$("conversa-col").classList.contains("vazia")) return;
  if (!conviteCabe()) {
    if (!caixa.hidden && animacoesLigadas() && caixa.firstElementChild) {
      sairDoAr(caixa, { aoFim: () => { caixa.hidden = true; caixa.innerHTML = ""; } });
    } else {
      caixa.hidden = true;
      caixa.innerHTML = "";
    }
    return;
  }
  const novo = caixa.hidden;
  caixa.hidden = false;
  const redesenhar = () => {
    caixa.innerHTML = '<div class="agora-cabeca"><span class="sv-kicker">Apoie o PAULUS</span></div>' + cartaoDoConvite("inicio");
    ligarConvite(caixa, redesenhar, () => desenharConviteNaInicio());
  };
  redesenhar();
  if (novo && animacoesLigadas()) entraConteudo(caixa);
}

(function () {
  const col = $("conversa-col");
  if (col && typeof MutationObserver === "function") {
    new MutationObserver(() => { if (col.classList.contains("vazia")) desenharConviteNaInicio(); }).observe(col, { attributes: true, attributeFilter: ["class"] });
  }
  desenharConviteNaInicio();
})();
