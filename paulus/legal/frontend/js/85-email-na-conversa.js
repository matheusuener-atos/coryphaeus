/* ---------------------------------------- o e-mail pela conversa (T3) */
/*
   Pacote de telas de 01/10/2026: `Conversa - E-mail` e `Conversa - Escrever
   e-mail` (src/email_pela_conversa.py).

   "Abra o ultimo e-mail do Mercado Pago": a conversa diz o que a mensagem e
   (por regra), o "Achei na mensagem" traz o codigo ou o prazo, e a mensagem
   aparece como o remetente desenhou - o mesmo quadro isolado da caixa
   (exModCorpo/exMontarHtml, js/29-email-caixa.js): sem script, imagens de
   fora bloqueadas ate a pessoa pedir. A caixa de pedido ganha "No e-mail" e
   "Na conversa": no e-mail, a pergunta e sobre a mensagem.

   "Responda a Priscila confirmando o acordo...": o envelope (De, Para,
   Assunto, Anexos) e as conferencias ficam na conversa, e o texto no lugar
   da caixa de pedido, com a faixa de formatacao, o pedido ao assistente
   (sobre o e-mail inteiro ou sobre o trecho selecionado) e Cancelar /
   Salvar rascunho / Enviar. O rascunho fica guardado na conversa. Enviar
   pede o sim e vai pela rota de sempre (/api/email/enviar): com Limites da
   IA mandando, vira pedido em Aprovacoes.
*/

const emc = {
  trabalho: "",      // a conversa em que o e-mail esta aberto
  aberto: null,      // {cabeca, m}: a mensagem aberta (a ultima pedida)
  modo: "email",     // a caixa de pedido: "email" (sobre a mensagem) ou "conversa"
  resp: null,        // o rascunho em edicao: {uid, conta_id, para, cc, cco, assunto, sobre, corpo, anexos, ...}
  caixaResp: null,   // o cartao do envelope, na conversa
  contas: null,
  salvando: 0,
  trecho: null,      // a selecao guardada para o pedido sobre o trecho
};
const EMC_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const EMC_SEM_RESPOSTA = /(no-?reply|nao-?respond|naorespond|do-?not-?reply|donotreply|mailer-daemon|notifica[cç]|bounce)/i;
const EMC_ATALHOS_TRECHO = [
  ["Deixar mais formal", "Reescreva este trecho em tom mais formal, como um advogado escreve a um cliente. Mantenha tudo o que ele diz."],
  ["Encurtar", "Reescreva este trecho mais curto, sem perder nome, data, valor ou pedido que estejam nele."],
];

function emcQuando(iso) {
  const d = new Date(iso || "");
  if (isNaN(d)) return "";
  return d.getDate() + " " + EMC_MESES[d.getMonth()] + " · " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

function emcIniciais(nome, email) {
  const partes = String(nome || email || "?").replace(/[<>"]/g, "").trim().split(/\s+/).filter(Boolean);
  const letras = partes.length > 1 ? partes[0][0] + partes[partes.length - 1][0] : (partes[0] || "?").slice(0, 2);
  return letras.toUpperCase();
}

/* ------------------------------------------------------------ o cartao */

function cartaoDeEmail(d) {
  const c = d.campos || {};
  const classe = "emc-cartao" + (c.acao === "responder" || c.acao === "escrever" ? " emc-resp-cartao" : "");
  return '<div class="' + classe + '" data-emc-uid="' + esc(c.uid || "") + '"><div class="emc-carregando">' + esqueleto("texto") + "</div></div>";
}

function ligarEmailNaProposta(caixa, d) {
  const c = d.campos || {};
  const alvo = caixa.querySelector(".emc-cartao");
  if (!alvo) return;
  emc.trabalho = estado.trabalhoId;
  if (c.acao === "responder" || c.acao === "escrever") {
    // A conversa reaberta nao chama o modelo de novo: o rascunho guardado
    // volta como estava; sem ele, o convite para escrever.
    if (caixa.dataset.propostaGuardada) return respostaGuardadaNaConversa(alvo, c);
    return abrirRespostaNaConversa(alvo, c, { pedido: c.pedido || "", comRascunho: true });
  }
  return abrirMensagemNaConversa(alvo, c);
}

async function respostaGuardadaNaConversa(alvo, c) {
  const r = await fetch("/api/email/conversa/rascunho?trabalho_id=" + encodeURIComponent(estado.trabalhoId) + "&uid=" + encodeURIComponent(c.uid)).catch(() => null);
  const tem = Boolean(r && r.ok);
  const novo = c.acao === "escrever";
  alvo.innerHTML = '<div class="emc-fechado">' + ic("draft", 16) + "<span>" + (tem ? "Rascunho guardado nesta conversa" : novo ? "O e-mail ainda não foi escrito" : "A resposta ainda não foi escrita") +
    " · “" + esc(c.assunto || (novo ? "e-mail para " + (c.quem || "") : "e-mail")) + "”</span>" +
    '<button type="button" class="emc-botao" data-emc-continuar="1">' + (tem ? "Continuar o rascunho" : novo ? "Escrever o e-mail" : "Escrever a resposta") + "</button></div>";
  alvo.querySelector("[data-emc-continuar]").onclick = () => abrirRespostaNaConversa(alvo, c, { pedido: c.pedido || "", comRascunho: !tem });
}

async function emcMensagem(uid, contaId) {
  const r = await fetch("/api/email/mensagem?uid=" + encodeURIComponent(uid) + "&conta_id=" + encodeURIComponent(contaId || "")).catch(() => null);
  if (!r || !r.ok) throw new Error(r ? await erroDe(r) : "sem resposta do servidor");
  return r.json();
}

/* A mensagem aberta: o "Achei na mensagem", o cartao com o cabecalho e as
   acoes, o corpo no quadro isolado e o pe (imagens, so o texto, a proxima). */
async function abrirMensagemNaConversa(alvo, c) {
  let m;
  try {
    m = await emcMensagem(c.uid, c.conta_id);
  } catch (err) {
    alvo.innerHTML = '<div class="emc-falta">' + ic("mail", 16) + "<span>Não consegui abrir “" + esc(c.assunto || "o e-mail") + "”: " + esc(err.message) + "</span></div>";
    return;
  }
  emc.aberto = { cabeca: c, m: m, alvo: alvo };
  emc.modo = "email";
  desenharMensagemNaConversa();
  atualizarModosDoEmail();
}

function achadoDaMensagem(c, m) {
  const codigo = c.codigo || "";
  if (codigo) {
    return '<div class="emc-achado"><span class="emc-kicker">Achei na mensagem</span>' +
      '<div class="emc-achado-linha"><div class="emc-achado-valor"><small>Código de verificação</small><b class="emc-codigo">' + esc(codigo) + "</b></div>" +
      '<button type="button" class="emc-botao" data-emc-copiar="' + esc(codigo) + '">' + ic("content_copy", 15) + "Copiar código</button></div>" +
      "<p>Por segurança, não compartilhe este código.</p></div>";
  }
  if (m.prazo) {
    return '<div class="emc-achado"><span class="emc-kicker">Achei na mensagem</span>' +
      '<div class="emc-achado-linha"><div class="emc-achado-valor"><small>Prazo</small><b class="emc-codigo">' + esc(dataCurta(m.prazo)) + "</b></div>" +
      '<button type="button" class="emc-botao" data-emc-prazo="1">' + ic("event", 15) + "Criar o prazo</button></div>" +
      (m.prazo_trecho ? "<p>“" + esc(m.prazo_trecho) + "”</p>" : "") + "</div>";
  }
  return "";
}

function desenharMensagemNaConversa() {
  const a = emc.aberto;
  if (!a) return;
  const { cabeca: c, m, alvo } = a;
  const soTexto = cx.soTexto === undefined ? emailPrefs().soTexto : cx.soTexto;
  const liberadas = exImagensLiberadas(m.uid);
  const html = m.html && !soTexto;
  const corpo = html
    ? '<div class="ex-html emc-folha"><iframe class="ex-html-quadro" data-ex-html="' + esc(m.uid) + '" title="Mensagem" ' +
      'sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer"></iframe></div>'
    : '<div class="emc-folha emc-folha-texto"><div class="ex-corpo">' + corpoComPrazo(m.corpo || "", m.prazo_trecho) + "</div></div>";
  const pe = [];
  if (html && m.imagens_remotas && !liberadas) {
    pe.push('<span class="emc-pe-item">' + ic("visibility_off", 15) + "imagens bloqueadas até você permitir</span>" +
      '<button type="button" class="sv-ligacao" data-emc-imagens="1">mostrar</button>');
  }
  if (m.html) pe.push('<button type="button" class="sv-ligacao" data-emc-texto="1">' + (html ? "ver só o texto" : "ver com a formatação") + "</button>");
  const para = Array.isArray(m.para) ? m.para.slice(0, 2).join(", ") : String(m.para || "");
  alvo.innerHTML = achadoDaMensagem(c, m) +
    '<div class="emc-msg">' +
    '<div class="emc-msg-cabeca"><span class="emc-avatar">' + esc(emcIniciais(m.de_nome, m.de_email)) + "</span>" +
    '<div class="emc-msg-quem"><div class="emc-msg-titulo"><h3>' + esc(m.assunto || "(sem assunto)") + '</h3><span class="emc-pasta">Caixa de entrada</span></div>' +
    '<div class="emc-msg-de"><b>' + esc(m.de_nome || m.de_email) + "</b>" + (m.de_nome ? "<span>‹" + esc(m.de_email) + "›</span>" : "") + "</div>" +
    (para ? "<small>para " + esc(para) + "</small>" : "") + "</div>" +
    '<div class="emc-msg-lado"><span class="emc-quando">' + esc(emcQuando(m.quando)) + "</span>" +
    '<div class="emc-msg-acoes"><button type="button" class="emc-botao" data-emc-responder="vazio">Responder</button>' +
    '<button type="button" class="emc-botao" data-emc-responder="encaminhar">Encaminhar</button>' +
    '<button type="button" class="primario emc-botao" data-emc-responder="assistente">' + ic("edit", 15) + "Rascunho pelo assistente</button>" +
    '<button type="button" class="botao-icone" data-emc-caixa="1" title="Abrir em E-mail" aria-label="Abrir em E-mail">' + ic("more_horiz", 17) + "</button>" +
    '<button type="button" class="botao-icone" data-emc-fechar="1" title="Fechar o e-mail" aria-label="Fechar o e-mail">' + ic("close", 17) + "</button></div></div></div>" +
    '<div class="emc-msg-corpo">' + corpo + "</div>" +
    '<div class="emc-msg-pe">' + pe.join('<i class="emc-pe-divisa"></i>') + '<span class="vazio-flex"></span>' +
    '<button type="button" class="sv-ligacao" data-emc-proxima="1">Próxima que pede resposta' + ic("chevron_right", 15) + "</button></div>" +
    "</div>" +
    '<p class="emc-nota">Li só esta mensagem. As outras continuam no seu servidor.</p>';
  if (html) exMontarHtml(alvo, m);
  ligarMensagemNaConversa(alvo, c, m);
  if (pertoDoFim()) rolar();
}

function ligarMensagemNaConversa(alvo, c, m) {
  const b = (sel) => alvo.querySelector(sel);
  if (b("[data-emc-copiar]")) b("[data-emc-copiar]").onclick = async (e) => {
    try { await navigator.clipboard.writeText(e.currentTarget.dataset.emcCopiar); avisoCert("código copiado", { tom: "ok" }); }
    catch (err) { avisoCert("não consegui copiar — selecione e copie à mão", { tom: "erro" }); }
  };
  if (b("[data-emc-prazo]")) b("[data-emc-prazo]").onclick = () => criarPrazoDoEmail(m, false);
  if (b("[data-emc-imagens]")) b("[data-emc-imagens]").onclick = () => {
    cx.imagensLiberadas = cx.imagensLiberadas || new Set();
    cx.imagensLiberadas.add(m.uid);
    desenharMensagemNaConversa();
  };
  if (b("[data-emc-texto]")) b("[data-emc-texto]").onclick = () => {
    const agora = cx.soTexto === undefined ? emailPrefs().soTexto : cx.soTexto;
    cx.soTexto = !agora;
    desenharMensagemNaConversa();
  };
  alvo.querySelectorAll("[data-emc-responder]").forEach((x) => {
    x.onclick = () => {
      const tipo = x.dataset.emcResponder;
      novaRespostaNaConversa(c, m, { comRascunho: tipo === "assistente", encaminhar: tipo === "encaminhar" });
    };
  });
  b("[data-emc-caixa]").onclick = async () => {
    marcarDestino("caixa");
    await mostrarEmail("caixa");
    if (typeof exAbrir === "function") exAbrir(m.uid);
  };
  b("[data-emc-fechar]").onclick = () => {
    alvo.innerHTML = '<div class="emc-fechado">' + ic("mail", 16) + "<span>“" + esc(m.assunto || "e-mail") + "” fechado</span>" +
      '<button type="button" class="emc-botao" data-emc-reabrir="1">Abrir de novo</button></div>';
    alvo.querySelector("[data-emc-reabrir]").onclick = () => abrirMensagemNaConversa(alvo, c);
    if (emc.aberto && emc.aberto.alvo === alvo) emc.aberto = null;
    atualizarModosDoEmail();
  };
  b("[data-emc-proxima]").onclick = () => proximaQuePedeResposta(c, m);
}

/* A proxima nao lida, ainda sem resposta, de um remetente que recebe
   resposta: abre embaixo, na conversa. */
async function proximaQuePedeResposta(c, m) {
  const r = await fetch("/api/email/caixa?filtro=nao_lidos&limite=20&conta_id=" + encodeURIComponent(c.conta_id || "")).catch(() => null);
  if (!r || !r.ok) { avisoCert(r ? await erroDe(r) : "sem resposta do servidor", { tom: "erro" }); return; }
  const lista = (await r.json()).mensagens || [];
  const prox = lista.find((x) => x.uid !== m.uid && !x.respondido && !EMC_SEM_RESPOSTA.test(String(x.de_email || "").split("@")[0]));
  if (!prox) { avisoCert("nenhuma outra mensagem não lida esperando resposta", { tom: "ok" }); return; }
  // Entra na conversa guardada (a fala e o cartão), e volta ao reabrir.
  const g = await fetch("/api/email/conversa/proxima", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trabalho_id: estado.trabalhoId, conta_id: c.conta_id || "", uid: prox.uid }),
  }).catch(() => null);
  if (!g || !g.ok) { avisoCert(g ? await erroDe(g) : "sem resposta do servidor", { tom: "erro" }); return; }
  const d = await g.json();
  const nota = document.createElement("div");
  nota.className = "resposta";
  nota.innerHTML = '<div class="texto">' + esc(d.texto) + "</div>" +
    '<div class="emc-cartao" data-emc-uid="' + esc(prox.uid) + '"><div class="emc-carregando">' + esqueleto("texto") + "</div></div>";
  $("centro").appendChild(nota);
  if (animacoesLigadas()) entraConteudo(nota);
  rolar();
  abrirMensagemNaConversa(nota.querySelector(".emc-cartao"), d.proposta.campos);
}

/* ------------------------------------- a caixa de pedido: no e-mail */

function emailNaConversaAberto() {
  return Boolean(emc.aberto && emc.trabalho === estado.trabalhoId && document.body.contains(emc.aberto.alvo));
}

function atualizarModosDoEmail() {
  const barra = $("emc-modos");
  const pedido = $("pedido");
  if (!barra || !pedido) return;
  const ativo = emailNaConversaAberto() && !emc.resp;
  barra.hidden = !ativo;
  // "No e-mail", a linha de onde a pergunta procura e a pilula do Acervo
  // nao valem: a pergunta vai para a mensagem.
  const col = $("conversa-col");
  if (col) col.classList.toggle("emc-no-email", ativo && emc.modo === "email");
  // So desfaz o texto que ele mesmo pos: os outros (a ficha, a agenda) ficam.
  const doEmail = "Pergunte sobre o e-mail, ou peça uma resposta…";
  if (ativo && emc.modo === "email") {
    if (pedido.placeholder !== doEmail) pedido.dataset.emcAntes = pedido.placeholder;
    pedido.placeholder = doEmail;
  } else if (pedido.placeholder === doEmail) {
    pedido.placeholder = pedido.dataset.emcAntes || "Pergunte outra coisa ou aponte outra pasta…";
  }
  if (!ativo) return;
  barra.querySelectorAll("[data-emc-modo]").forEach((x) => x.classList.toggle("ativa", x.dataset.emcModo === emc.modo));
  barra.querySelectorAll("[data-emc-atalho]").forEach((x) => { x.hidden = emc.modo !== "email"; });
}

function fecharEmailNaConversa() {
  emc.aberto = null;
  if (emc.resp) fecharEditorDoEmail(true);
  emc.resp = null;
  atualizarModosDoEmail();
}

/* "No e-mail": a pergunta vai com a mensagem (o texto do remetente cercado
   no servidor), e as duas falas entram na conversa. */
async function perguntarSobreOEmail(pergunta) {
  const a = emc.aberto;
  const centro = $("centro");
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(pergunta));
  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = '<div class="texto em-andamento ativo">' + coroa(16) + "Lendo o e-mail…</div>";
  centro.appendChild(resposta);
  rolar();
  const r = await fetch("/api/email/conversa/perguntar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trabalho_id: estado.trabalhoId, uid: a.m.uid, conta_id: a.cabeca.conta_id || "", pergunta: pergunta }),
  }).catch(() => null);
  if (!r || !r.ok) {
    resposta.innerHTML = '<div class="texto">Não consegui responder: ' + esc(r ? await erroDe(r) : "sem resposta do servidor") + "</div>";
    return;
  }
  const d = await r.json();
  resposta.innerHTML = '<div class="texto">' + esc(d.texto) + "</div>" + (d.aviso ? '<p class="emc-aviso">' + ic("error", 15) + esc(d.aviso) + "</p>" : "");
  rolar();
}

/* "Achar prazos": por regra, o prazo que o servidor achou na mensagem. */
function acharPrazosNoEmail() {
  const m = emc.aberto.m;
  const nota = document.createElement("div");
  nota.className = "resposta";
  nota.innerHTML = m.prazo
    ? '<div class="texto">Achei um prazo: ' + esc(dataCurta(m.prazo)) + (m.prazo_trecho ? " (“" + esc(m.prazo_trecho) + "”)" : "") + ".</div>" +
      '<div class="linha-form"><button type="button" data-emc-criar-prazo="1">Criar o prazo</button></div>'
    : '<div class="texto">Não achei prazo nesta mensagem (procuro data perto de “prazo”, “vence”, “até o dia”, “audiência”…).</div>';
  $("centro").appendChild(nota);
  const b = nota.querySelector("[data-emc-criar-prazo]");
  if (b) b.onclick = () => criarPrazoDoEmail(m, false);
  rolar();
}

function ligarModosDoEmail() {
  const barra = $("emc-modos");
  if (!barra || barra.dataset.ligada) return;
  barra.dataset.ligada = "1";
  barra.querySelectorAll("[data-emc-modo]").forEach((x) => {
    x.onclick = () => { emc.modo = x.dataset.emcModo; atualizarModosDoEmail(); $("pedido").focus(); };
  });
  barra.querySelectorAll("[data-emc-atalho]").forEach((x) => {
    x.onclick = () => {
      if (!emailNaConversaAberto()) return;
      const qual = x.dataset.emcAtalho;
      if (qual === "resumir") perguntarSobreOEmail("Resuma este e-mail.");
      else if (qual === "prazos") acharPrazosNoEmail();
      else novaRespostaNaConversa(emc.aberto.cabeca, emc.aberto.m, { comRascunho: true });
    };
  });
}

/* O gancho de enviar(): com o e-mail aberto e "No e-mail", a pergunta e
   sobre ele. Devolve true quando tratou. */
function pedidoNoEmail(pedido) {
  if (!emailNaConversaAberto() || emc.resp || emc.modo !== "email") return false;
  perguntarSobreOEmail(pedido);
  return true;
}

/* ------------------------------------------------------- a resposta */

/* Pelos botoes do cartao: o envelope entra no fim da conversa. */
function novaRespostaNaConversa(c, m, o) {
  const nota = document.createElement("div");
  nota.className = "resposta";
  nota.innerHTML = '<div class="emc-cartao emc-resp-cartao" data-emc-uid="' + esc(m.uid) + '"></div>';
  $("centro").appendChild(nota);
  if (animacoesLigadas()) entraConteudo(nota);
  abrirRespostaNaConversa(nota.firstElementChild, Object.assign({}, c, { uid: m.uid }), o, m);
}

async function emcContas() {
  if (emc.contas) return emc.contas;
  try {
    const d = await (await fetch("/api/email/contas")).json();
    emc.contas = d.contas || [];
  } catch (err) { emc.contas = []; }
  return emc.contas;
}

/* O envelope na conversa e o texto no lugar da caixa de pedido. Com um
   rascunho ja guardado nesta conversa, ele volta como estava. */
async function abrirRespostaNaConversa(alvo, c, o, m) {
  o = o || {};
  // Um rascunho por vez na caixa de pedido: o que estava aberto fica guardado.
  if (emc.resp) { await salvarRascunhoDoEmail(); fecharEditorDoEmail(false); }
  emc.trabalho = estado.trabalhoId;
  emc.caixaResp = alvo;
  let guardado = null;
  const r = await fetch("/api/email/conversa/rascunho?trabalho_id=" + encodeURIComponent(estado.trabalhoId) + "&uid=" + encodeURIComponent(c.uid)).catch(() => null);
  if (r && r.ok) guardado = await r.json();
  if (guardado) {
    emc.resp = guardado;
  } else if (c.acao === "escrever") {
    // O e-mail novo: sem mensagem de origem; quem recebe veio da ficha ou da frase.
    emc.resp = {
      uid: c.uid, conta_id: c.conta_id || "", de: c.conta_email || "", sobre: "", novo_email: true,
      // "Envie a procuração por e-mail para...": o documento já vem anexado.
      para: (c.para || []).slice(), cc: [], cco: [], assunto: c.assunto || "", corpo: "", corpo_html: "", anexos: (c.anexos || []).slice(), conferencias: [],
      pelo_assistente: false, palavras: 0, salvo_em: "", novo: true,
    };
  } else {
    if (!m) {
      try { m = await emcMensagem(c.uid, c.conta_id); } catch (err) { m = { uid: c.uid, de_nome: c.de_nome, de_email: c.de_email, assunto: c.assunto, corpo: "" }; }
    }
    const assunto = o.encaminhar
      ? (/^(fwd?|enc):/i.test(m.assunto || "") ? m.assunto : "Enc: " + (m.assunto || ""))
      : (/^re:/i.test(m.assunto || "") ? m.assunto : "Re: " + (m.assunto || ""));
    const citacao = o.encaminhar
      ? "\n\n---------- Mensagem encaminhada ----------\nDe: " + (m.de_nome || "") + " <" + (m.de_email || "") + ">\nAssunto: " + (m.assunto || "") + "\n\n" + (m.corpo || "")
      : "";
    emc.resp = {
      uid: c.uid, conta_id: c.conta_id || "", de: c.conta_email || "", sobre: m.assunto || "",
      para: o.encaminhar ? [] : [{ nome: m.de_nome || "", email: m.de_email || "" }], cc: [], cco: [],
      assunto: assunto, corpo: citacao.trim() ? citacao : "", corpo_html: "", anexos: [], conferencias: [],
      pelo_assistente: false, palavras: 0, salvo_em: "", novo: true,
      responder_a: o.encaminhar ? "" : (m.message_id || ""), referencias: o.encaminhar ? "" : (m.referencias || ""),
    };
  }
  // Encaminhar leva os anexos da mensagem (js/18-email.js, anexosParaEncaminhar).
  if (!guardado && o.encaminhar && m && (m.anexos || []).length) {
    emc.resp.anexos = (await anexosParaEncaminhar(m, c.conta_id)).map((a) => a.path);
  }
  emc.resp.estado = guardado || !o.comRascunho ? "pronto" : "escrevendo";
  await emcContas();
  desenharEnvelope();
  abrirEditorDoEmail();
  atualizarModosDoEmail();
  if (emc.resp.estado === "escrevendo") escreverRascunhoDoEmail(o.pedido || "");
}

async function escreverRascunhoDoEmail(pedido) {
  const resp = emc.resp;
  desenharEditorDoEmail();
  const r = await fetch("/api/email/conversa/rascunho", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trabalho_id: estado.trabalhoId, uid: resp.uid, conta_id: resp.conta_id, pedido: pedido, para: resp.para }),
  }).catch(() => null);
  if (emc.resp !== resp) return;
  if (!r || !r.ok) {
    resp.estado = "pronto";
    desenharEditorDoEmail();
    avisoCert("não escrevi o rascunho: " + (r ? await erroDe(r) : "sem resposta do servidor"), { tom: "erro" });
    return;
  }
  const d = await r.json();
  Object.assign(resp, d, { estado: "pronto", novo: false });
  // A frase da conversa passou a ser "Preparei a resposta..." (o servidor
  // trocou na conversa guardada); aqui, a bolha acompanha.
  const fala = emc.caixaResp && emc.caixaResp.closest(".resposta");
  const texto = fala && fala.querySelector(".texto");
  if (texto && resp.novo_email && /^(Vou escrever o e-mail|Não achei e-mail de)/.test(texto.textContent)) {
    texto.textContent = "Preparei o e-mail. O texto está na caixa abaixo para você revisar — " +
      ((resp.conferencias || []).some((x) => /Aprovações/.test(x.texto)) ? "enviar passa por Aprovações." : "nada sai sem o seu clique em Enviar.");
  }
  if (texto && /^Vou escrever a resposta/.test(texto.textContent)) {
    texto.textContent = "Preparei a resposta. O texto está na caixa abaixo para você revisar — " +
      ((resp.conferencias || []).some((x) => /Aprovações/.test(x.texto)) ? "enviar passa por Aprovações." : "nada sai sem o seu clique em Enviar.");
  }
  desenharEnvelope();
  desenharEditorDoEmail();
}

function emcChipDeEndereco(x, i, chave) {
  return '<span class="emc-chip" title="' + esc(x.email) + '"><span class="emc-chip-avatar">' + esc(emcIniciais(x.nome, x.email)) + "</span>" +
    (x.nome ? "<b>" + esc(x.nome) + "</b><small>‹" + esc(x.email) + "›</small>" : "<b>" + esc(x.email) + "</b>") +
    '<button type="button" data-emc-tirar="' + chave + ":" + i + '" title="Tirar" aria-label="Tirar ' + esc(x.email) + '">' + ic("close", 14) + "</button></span>";
}

function emcLinhaDeEnderecos(rotulo, chave, extra) {
  const lista = emc.resp[chave] || [];
  return '<div class="emc-campo"><label for="emc-add-' + chave + '">' + rotulo + '</label><div class="emc-campo-miolo">' +
    lista.map((x, i) => emcChipDeEndereco(x, i, chave)).join("") +
    '<input type="text" class="emc-add" id="emc-add-' + chave + '" data-emc-add="' + chave + '" placeholder="adicionar…" autocomplete="off"></div>' + (extra || "") + "</div>";
}

/* O envelope: Resposta a "...", De, Para (CC e CCO quando pedidos), Assunto e
   Anexos; embaixo, as conferencias. */
function desenharEnvelope() {
  const alvo = emc.caixaResp;
  const resp = emc.resp;
  if (!alvo || !resp) return;
  const contas = emc.contas || [];
  const de = contas.length > 1
    ? '<select class="emc-de" id="emc-de" title="De que conta sai">' + contas.map((x) => '<option value="' + esc(x.id) + '"' + (x.id === resp.conta_id ? " selected" : "") + ">" + esc(x.email) + "</option>").join("") + "</select>"
    : '<span class="emc-de-uma">' + ic("mail", 15) + "<b>" + esc(resp.de || (contas[0] || {}).email || "") + "</b></span>";
  const comCopia = resp.cc.length || resp.cco.length || resp.mostrarCopia;
  const anexos = (resp.anexos || []).map((p, i) => {
    const nome = String(p).split(/[\\/]/).pop();
    return '<span class="emc-chip emc-anexo" title="' + esc(p) + '">' + glifo(nome) + "<b>" + esc(nome) + "</b>" +
      '<button type="button" data-emc-tirar="anexos:' + i + '" title="Tirar este anexo" aria-label="Tirar ' + esc(nome) + '">' + ic("close", 14) + "</button></span>";
  }).join("");
  const salvo = resp.estado === "escrevendo" ? "escrevendo…" : resp.enviado ? resp.enviado : resp.salvo_em ? "rascunho salvo " + emcHaPouco(resp.salvo_em) : "ainda não salvo";
  alvo.innerHTML = '<div class="emc-env">' +
    '<div class="emc-env-cabeca">' + (resp.novo_email ? ic("edit_note", 16) + "<b>Novo e-mail</b>" + (resp.para.length ? "<span>para " + esc(resp.para[0].nome || resp.para[0].email) + "</span>" : "")
      : ic(/^enc:/i.test(resp.assunto) ? "forward" : "reply", 16) + "<b>" + (/^enc:/i.test(resp.assunto) ? "Encaminhar" : "Resposta") + "</b>" +
        "<span>a “" + esc(resp.sobre || resp.assunto) + "”</span>") + "<span class=\"vazio-flex\"></span>" +
    '<span class="emc-salvo' + (resp.salvo_em ? " ok" : "") + '">' + esc(salvo) + "</span></div>" +
    '<div class="emc-campo"><label>De</label><div class="emc-campo-miolo">' + de + "</div></div>" +
    emcLinhaDeEnderecos("Para", "para", comCopia ? "" : '<button type="button" class="sv-ligacao emc-copia" data-emc-copia="1">CC · CCO</button>') +
    (comCopia ? emcLinhaDeEnderecos("CC", "cc") + emcLinhaDeEnderecos("CCO", "cco") : "") +
    '<div class="emc-campo"><label for="emc-assunto">Assunto</label><div class="emc-campo-miolo"><input type="text" class="emc-assunto" id="emc-assunto" value="' + esc(resp.assunto) + '"></div></div>' +
    '<div class="emc-campo"><label>Anexos</label><div class="emc-campo-miolo">' + anexos +
    '<button type="button" class="sv-ligacao emc-anexar" data-emc-anexar="1">' + ic("add", 15) + "do Acervo ou do computador</button></div></div>" +
    "</div>" +
    '<div class="emc-confere">' + (resp.conferencias || []).map((x) =>
      '<span class="emc-confere-item' + (x.ok ? " ok" : " olhar") + '">' + ic(x.icone || (x.ok ? "check_circle" : "schedule"), 15) + esc(x.texto) + "</span>").join("") + "</div>";
  ligarEnvelope(alvo);
}

function emcHaPouco(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 90) return "agora";
  return "às " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

function ligarEnvelope(alvo) {
  const resp = emc.resp;
  const de = alvo.querySelector("#emc-de");
  if (de) de.onchange = () => {
    resp.conta_id = de.value;
    resp.de = ((emc.contas || []).find((x) => x.id === de.value) || {}).email || "";
    salvarRascunhoDoEmail();
  };
  const copia = alvo.querySelector("[data-emc-copia]");
  if (copia) copia.onclick = () => { resp.mostrarCopia = true; desenharEnvelope(); alvo.querySelector("#emc-add-cc").focus(); };
  alvo.querySelectorAll("[data-emc-add]").forEach((campo) => {
    const chave = campo.dataset.emcAdd;
    const juntar = () => {
      const achados = enderecosDe(campo.value);
      if (!achados.length) return;
      achados.forEach((email) => {
        if (!resp[chave].some((x) => x.email.toLowerCase() === email.toLowerCase())) resp[chave].push({ nome: "", email: email });
      });
      campo.value = "";
      desenharEnvelope();
      salvarRascunhoDoEmail();
      const de_novo = emc.caixaResp.querySelector('[data-emc-add="' + chave + '"]');
      if (de_novo) de_novo.focus();
    };
    campo.onkeydown = (e) => { if (e.key === "Enter" || e.key === "," || e.key === ";") { e.preventDefault(); juntar(); } };
    campo.onblur = juntar;
  });
  alvo.querySelectorAll("[data-emc-tirar]").forEach((x) => {
    x.onclick = () => {
      const [chave, i] = x.dataset.emcTirar.split(":");
      resp[chave].splice(Number(i), 1);
      desenharEnvelope();
      salvarRascunhoDoEmail();
    };
  });
  const assunto = alvo.querySelector("#emc-assunto");
  assunto.oninput = () => { resp.assunto = assunto.value; agendarSalvarEmail(); };
  alvo.querySelector("[data-emc-anexar]").onclick = () => abrirAnexar({
    titulo: "Anexar à resposta", contexto: "Conversa › E-mail", verbo: "Anexar",
    aoCaminhos: async (caminhos) => {
      const novos = (caminhos || []).filter((p) => !resp.anexos.includes(p));
      if (!novos.length) return;
      const r = await fetch("/api/email/anexos/conferir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminhos: novos }) }).catch(() => null);
      const conferidos = r && r.ok ? (await r.json()).anexos.filter((a) => a.existe) : novos.map((p) => ({ path: p }));
      resp.anexos = resp.anexos.concat(conferidos.map((a) => a.path));
      if (conferidos.some((a) => a.grande)) avisoCert("um dos arquivos passa de 20 MB — o servidor de e-mail costuma recusar", { tom: "erro" });
      desenharEnvelope();
      salvarRascunhoDoEmail();
    },
  });
}

/* --------------------------------- o texto, no lugar da caixa de pedido */

function abrirEditorDoEmail() {
  const editor = $("emc-editor");
  const campo = $("cartao-campo");
  if (!editor || !campo) return;
  campo.hidden = true;
  editor.hidden = false;
  desenharEditorDoEmail();
  if (animacoesLigadas()) entraConteudo(editor);
}

function fecharEditorDoEmail(semPerguntar) {
  const editor = $("emc-editor");
  if (editor) { editor.hidden = true; editor.innerHTML = ""; }
  if ($("cartao-campo")) $("cartao-campo").hidden = false;
  fecharTrechoDoEmail();
  const resp = emc.resp;
  emc.resp = null;
  if (!semPerguntar && emc.caixaResp && resp && !resp.enviado) {
    const alvo = emc.caixaResp;
    const c = { uid: resp.uid, conta_id: resp.conta_id, conta_email: resp.de, assunto: resp.sobre,
      acao: resp.novo_email ? "escrever" : "responder", para: resp.para };
    alvo.innerHTML = '<div class="emc-fechado">' + ic("draft", 16) + "<span>" + (resp.salvo_em ? "Rascunho guardado nesta conversa" : "Resposta deixada de lado") +
      " · “" + esc(resp.assunto) + "”</span>" + '<button type="button" class="emc-botao" data-emc-continuar="1">' + (resp.salvo_em ? "Continuar o rascunho" : "Escrever de novo") + "</button></div>";
    alvo.querySelector("[data-emc-continuar]").onclick = () => abrirRespostaNaConversa(alvo, c, {});
  }
  atualizarModosDoEmail();
}

function desenharEditorDoEmail() {
  const editor = $("emc-editor");
  const resp = emc.resp;
  if (!editor || !resp) return;
  const escrevendo = resp.estado === "escrevendo";
  const autoria = resp.pelo_assistente ? "escrito pelo assistente · " : "";
  if (!editor.querySelector("#emc-texto")) {
    editor.innerHTML = editorRico({ id: "emc-texto", classe: "emc-er", html: resp.corpo_html || "", texto: resp.corpo_html ? "" : resp.corpo, placeholder: "Escreva a resposta…" }) +
      '<div class="emc-pedir"><span class="ic ic-18">forum</span>' +
      '<input type="text" id="emc-pedir" placeholder="Peça ao assistente sobre o e-mail inteiro — ou selecione um trecho" autocomplete="off">' +
      '<kbd class="emc-tecla" title="Aperte / para pedir">/</kbd>' +
      '<button type="button" class="emc-mandar" id="emc-pedir-ir" title="Pedir" aria-label="Pedir">' + ic("arrow_upward", 16) + "</button></div>" +
      '<div class="emc-rodape"><button type="button" class="botao-icone" id="emc-anexar-pe" title="Anexar" aria-label="Anexar">' + ic("attach_file", 17) + "</button>" +
      '<button type="button" class="botao-icone" id="emc-ditar" title="Ditar — o texto entra no fim do e-mail" aria-label="Ditar no e-mail">' + ic("mic", 17) + "</button>" +
      '<span class="vazio-flex"></span><button type="button" class="emc-sem-borda" id="emc-cancelar">Cancelar</button>' +
      '<button type="button" class="emc-botao" id="emc-salvar">Salvar rascunho</button>' +
      '<button type="button" class="primario emc-enviar" id="emc-enviar">Enviar<span class="emc-enviar-ic">' + ic("arrow_upward", 15) + "</span></button></div>" +
      '<div class="emc-trecho" id="emc-trecho" hidden></div>';
    const barra = editor.querySelector(".er-barra");
    barra.insertAdjacentHTML("beforeend", '<span class="vazio-flex"></span><span class="emc-autoria" id="emc-autoria"></span>');
    ligarEditorDoEmail(editor);
  }
  const texto = $("emc-texto");
  if (escrevendo) {
    texto.readOnly = true;
    texto.closest(".er").classList.add("emc-escrevendo");
    $("emc-autoria").innerHTML = coroa(14) + "escrevendo a resposta nesta máquina…";
  } else {
    if (texto.readOnly) {
      texto.readOnly = false;
      texto.closest(".er").classList.remove("emc-escrevendo");
      if (resp.corpo_html) texto.html = resp.corpo_html; else texto.value = resp.corpo || "";
    }
    $("emc-autoria").textContent = autoria + plural(resp.palavras || palavrasDe(texto.value), "palavra");
  }
  $("emc-enviar").disabled = escrevendo;
  $("emc-salvar").disabled = escrevendo;
}

/* O ditado do editor do e-mail terminou (js/03-assistente.js,
   levarDitadoParaCaixa): o texto entra no fim do e-mail, como se digitado -
   o editor salva sozinho. Sem o editor aberto, devolve false e o texto vai
   para a caixa de pedido. */
function levarDitadoAoEmail(texto) {
  const campo = $("emc-texto");
  if (!campo || !emc.resp || !campo.isContentEditable || !String(texto || "").trim()) return false;
  campo.focus();
  const faixa = document.createRange();
  faixa.selectNodeContents(campo);
  faixa.collapse(false);
  const sel = getSelection();
  sel.removeAllRanges();
  sel.addRange(faixa);
  const antes = campo.textContent || "";
  const junto = (antes.trim() && !/\s$/.test(antes) ? " " : "") + String(texto).trim();
  if (!document.execCommand("insertText", false, junto)) {
    campo.value = (campo.value || "").replace(/\s+$/, "") + junto;
    campo.dispatchEvent(new Event("input", { bubbles: true }));
  }
  return true;
}

function palavrasDe(texto) {
  return (String(texto || "").match(/[\p{L}\p{N}_]+/gu) || []).length;
}

function ligarEditorDoEmail(editor) {
  const texto = ligarEditorRico("emc-texto", () => {
    if (!emc.resp || emc.resp.estado === "escrevendo") return;
    emc.resp.corpo = texto.value;
    emc.resp.corpo_html = texto.html;
    emc.resp.palavras = palavrasDe(texto.value);
    $("emc-autoria").textContent = (emc.resp.pelo_assistente ? "escrito pelo assistente · " : "") + plural(emc.resp.palavras, "palavra");
    agendarSalvarEmail();
  });
  if (texto && texto.querySelector) {
    texto.addEventListener("mouseup", () => setTimeout(abrirTrechoDoEmail, 0));
    texto.addEventListener("keyup", (e) => { if (e.shiftKey) abrirTrechoDoEmail(); });
    texto.addEventListener("keydown", (e) => { if (e.key === "/" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $("emc-pedir").focus(); } });
  }
  const pedir = $("emc-pedir");
  pedir.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); pedirNoEmailInteiro(pedir.value); } };
  $("emc-pedir-ir").onclick = () => pedirNoEmailInteiro(pedir.value);
  $("emc-anexar-pe").onclick = () => { const b = emc.caixaResp && emc.caixaResp.querySelector("[data-emc-anexar]"); if (b) b.click(); };
  $("emc-ditar").onclick = () => {
    if (ditado.estado) { avisoCert("já há um ditado aberto — conclua ou cancele antes"); return; }
    ditado.destino = "email";
    comecarDitado().then(() => { if (!ditado.estado) ditado.destino = ""; });
  };
  $("emc-cancelar").onclick = () => fecharEditorDoEmail(false);
  $("emc-salvar").onclick = async () => { await salvarRascunhoDoEmail(); avisoCert("rascunho salvo nesta conversa", { tom: "ok" }); };
  $("emc-enviar").onclick = enviarRespostaDaConversa;
}

/* "/" fora de um campo leva ao pedido ao assistente. */
document.addEventListener("keydown", (e) => {
  if (e.key !== "/" || !emc.resp || e.ctrlKey || e.metaKey || e.altKey) return;
  const foco = document.activeElement;
  if (foco && (foco.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(foco.tagName))) return;
  const pedir = $("emc-pedir");
  if (pedir && !pedir.closest("[hidden]")) { e.preventDefault(); pedir.focus(); }
});

let emcTimer = 0;
function agendarSalvarEmail() {
  clearTimeout(emcTimer);
  emcTimer = setTimeout(() => salvarRascunhoDoEmail(), 2500);
}

/* Guarda na conversa e refaz as conferencias (os valores, as datas). */
async function salvarRascunhoDoEmail() {
  clearTimeout(emcTimer);
  const resp = emc.resp;
  if (!resp || resp.estado === "escrevendo") return;
  const texto = $("emc-texto");
  if (texto) { resp.corpo = texto.value; resp.corpo_html = texto.html; }
  const vez = ++emc.salvando;
  const r = await fetch("/api/email/conversa/rascunho", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trabalho_id: estado.trabalhoId, uid: resp.uid, conta_id: resp.conta_id, para: resp.para, cc: resp.cc, cco: resp.cco,
      assunto: resp.assunto, corpo: resp.corpo, corpo_html: resp.corpo_html, anexos: resp.anexos, pelo_assistente: resp.pelo_assistente,
      responder_a: resp.responder_a || "", referencias: resp.referencias || "", novo_email: Boolean(resp.novo_email) }),
  }).catch(() => null);
  if (vez !== emc.salvando || emc.resp !== resp) return;
  if (!r || !r.ok) { avisoCert("não salvei o rascunho: " + (r ? await erroDe(r) : "sem resposta"), { tom: "erro" }); return; }
  const d = await r.json();
  resp.salvo_em = d.salvo_em;
  resp.conferencias = d.conferencias || [];
  resp.novo = false;
  const foco = document.activeElement && document.activeElement.id;
  const cursor = foco === "emc-assunto" ? $("emc-assunto").selectionStart : null;
  desenharEnvelope();
  if (foco === "emc-assunto") { const a = $("emc-assunto"); a.focus(); if (cursor !== null) a.setSelectionRange(cursor, cursor); }
}

/* O pedido sobre o e-mail inteiro: o texto todo e trocado pela versao do
   assistente, como uma edicao so (Desfazer volta). */
async function pedirNoEmailInteiro(pedido) {
  pedido = String(pedido || "").trim();
  const resp = emc.resp;
  const texto = $("emc-texto");
  if (!pedido || !resp || !texto || resp.estado === "escrevendo") return;
  const sel = window.getSelection();
  if (texto.contains(sel.anchorNode) && !sel.isCollapsed) { pedirNoTrecho(pedido); return; }
  $("emc-pedir").value = "";
  resp.estado = "escrevendo";
  desenharEditorDoEmail();
  const r = await fetch("/api/email/reescrever", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pedido: pedido, assunto: resp.assunto, corpo: resp.corpo || texto.value }),
  }).catch(() => null);
  resp.estado = "pronto";
  if (!r || !r.ok) {
    desenharEditorDoEmail();
    avisoCert("não mudei o texto: " + (r ? await erroDe(r) : "sem resposta"), { tom: "erro" });
    return;
  }
  const d = await r.json();
  texto.readOnly = false;
  texto.closest(".er").classList.remove("emc-escrevendo");
  texto.focus();
  document.execCommand("selectAll", false, null);
  document.execCommand("insertHTML", false, erTextoParaHtml(d.sugestao || ""));
  resp.pelo_assistente = true;
  desenharEditorDoEmail();
  salvarRascunhoDoEmail();
}

/* O trecho selecionado: a caixinha do pedido aparece junto dele. */
function abrirTrechoDoEmail() {
  const texto = $("emc-texto");
  const caixa = $("emc-trecho");
  if (!texto || !caixa || !emc.resp || emc.resp.estado === "escrevendo") return;
  const sel = window.getSelection();
  if (!sel.rangeCount || sel.isCollapsed || !texto.contains(sel.anchorNode) || !sel.toString().trim()) { if (!caixa.contains(document.activeElement)) fecharTrechoDoEmail(); return; }
  emc.trecho = sel.getRangeAt(0).cloneRange();
  const editor = $("emc-editor");
  const r = emc.trecho.getBoundingClientRect();
  const base = editor.getBoundingClientRect();
  caixa.innerHTML = '<div class="emc-trecho-linha"><span class="ic ic-16">forum</span><input type="text" id="emc-trecho-pedido" placeholder="Peça sobre o trecho…" autocomplete="off">' +
    '<button type="button" class="emc-mandar" data-emc-trecho-ir="1" title="Pedir" aria-label="Pedir">' + ic("arrow_upward", 15) + "</button></div>" +
    '<div class="emc-trecho-atalhos">' + EMC_ATALHOS_TRECHO.map(([rotulo], i) => '<button type="button" class="emc-atalho" data-emc-trecho-atalho="' + i + '">' + rotulo + "</button>").join("") +
    '<button type="button" class="emc-atalho" data-emc-trecho-conferir="1">Conferir os valores</button></div>';
  caixa.hidden = false;
  const largura = Math.min(460, base.width - 24);
  const esquerda = Math.max(12, Math.min(r.left - base.left, base.width - largura - 12));
  caixa.style.width = largura + "px";
  caixa.style.left = esquerda + "px";
  caixa.style.top = Math.max(8, r.bottom - base.top + 6) + "px";
  const campo = $("emc-trecho-pedido");
  campo.onkeydown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); pedirNoTrecho(campo.value); }
    if (e.key === "Escape") { e.preventDefault(); fecharTrechoDoEmail(); texto.focus(); }
  };
  caixa.querySelector("[data-emc-trecho-ir]").onclick = () => pedirNoTrecho(campo.value);
  caixa.querySelectorAll("[data-emc-trecho-atalho]").forEach((b) => { b.onclick = () => pedirNoTrecho(EMC_ATALHOS_TRECHO[Number(b.dataset.emcTrechoAtalho)][1]); });
  caixa.querySelector("[data-emc-trecho-conferir]").onclick = async () => {
    fecharTrechoDoEmail();
    await salvarRascunhoDoEmail();
    const linha = emc.caixaResp && emc.caixaResp.querySelector(".emc-confere");
    if (linha) { linha.scrollIntoView({ block: "nearest", behavior: animacoesLigadas() ? "smooth" : "auto" }); linha.classList.add("emc-pisca"); setTimeout(() => linha.classList.remove("emc-pisca"), 1200); }
  };
}

function fecharTrechoDoEmail() {
  const caixa = $("emc-trecho");
  if (caixa) { caixa.hidden = true; caixa.innerHTML = ""; }
  emc.trecho = null;
}

/* O trecho reescrito entra no lugar dele, sublinhado: e o que o assistente
   mudou. Desfazer volta. */
async function pedirNoTrecho(pedido) {
  pedido = String(pedido || "").trim();
  const resp = emc.resp;
  const faixa = emc.trecho;
  if (!pedido || !resp || !faixa) return;
  const original = faixa.toString();
  const caixa = $("emc-trecho");
  caixa.querySelector(".emc-trecho-linha").innerHTML = coroa(15) + "<span>reescrevendo o trecho…</span>";
  const r = await fetch("/api/email/reescrever", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pedido: pedido + " Devolva só o trecho reescrito.", assunto: resp.assunto, corpo: original }),
  }).catch(() => null);
  if (!r || !r.ok) { fecharTrechoDoEmail(); avisoCert("não mudei o trecho: " + (r ? await erroDe(r) : "sem resposta"), { tom: "erro" }); return; }
  const d = await r.json();
  const texto = $("emc-texto");
  texto.focus();
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(faixa);
  document.execCommand("insertHTML", false, '<span class="emc-mudou">' + esc(String(d.sugestao || "").trim()) + "</span>&#8203;");
  fecharTrechoDoEmail();
  resp.pelo_assistente = true;
  salvarRascunhoDoEmail();
}

/* Enviar: o sim primeiro, com o que vai acontecer em palavras; depois a rota
   de sempre. O resultado entra na conversa. */
async function enviarRespostaDaConversa() {
  const resp = emc.resp;
  if (!resp) return;
  const texto = $("emc-texto");
  resp.corpo = texto.value;
  resp.corpo_html = texto.html;
  const para = resp.para.map((x) => x.email);
  if (!para.length) { avisoCert("falta para quem vai", { tom: "erro" }); const p = document.querySelector('[data-emc-add="para"]'); if (p) p.focus(); return; }
  if (!resp.corpo.trim()) { avisoCert(resp.novo_email ? "o e-mail está vazio" : "a resposta está vazia", { tom: "erro" }); texto.focus(); return; }
  await salvarRascunhoDoEmail();
  const fila = (resp.conferencias || []).some((x) => /Aprovações/.test(x.texto));
  const olhar = (resp.conferencias || []).filter((x) => !x.ok).map((x) => x.texto);
  const sim = await confirmar({
    titulo: resp.novo_email ? "Enviar o e-mail?" : "Enviar a resposta?", contexto: "Conversa › E-mail",
    texto: ["Para " + resp.para.map((x) => x.nome || x.email).join(", ") + ", da conta " + (resp.de || "em uso") + ": “" + resp.assunto + "”" +
            (resp.anexos.length ? ", com " + plural(resp.anexos.length, "anexo") : "") + ".",
            fila ? "Vai para Aprovações: só sai depois do sim lá." : "Sai agora. Não dá para desfazer."].concat(olhar.length ? ["Ainda para olhar: " + olhar.join("; ") + "."] : []).join("\n"),
    confirmar: fila ? "Mandar para Aprovações" : "Enviar",
  });
  if (!sim) return;
  $("emc-enviar").disabled = true;
  const d = await mandarPedido({
    conta_id: resp.conta_id, para: para.join(", "), cc: resp.cc.map((x) => x.email).join(", "), cco: resp.cco.map((x) => x.email).join(", "),
    assunto: resp.assunto, corpo: resp.corpo, corpo_html: resp.corpo_html, anexos: resp.anexos,
    // A resposta encadeada (o Message-ID da mensagem); o e-mail novo e o encaminhado não têm.
    responder_a: /^enc:/i.test(resp.assunto) || resp.novo_email ? "" : (resp.responder_a || ""), referencias: resp.referencias || "",
  });
  if (!d) { $("emc-enviar").disabled = false; return; }
  const aguardando = Boolean(d.aguardando_aprovacao);
  resp.enviado = aguardando ? "esperando o seu sim em Aprovações" : "enviado " + emcHaPouco(new Date().toISOString());
  const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo: "email", campos: { aguardando: aguardando, para: para, assunto: resp.assunto } }),
  }).catch(() => null);
  const feito = r && r.ok ? await r.json() : null;
  const alvo = emc.caixaResp;
  emc.resp = resp;
  desenharEnvelope();
  alvo.querySelectorAll("input, select, button").forEach((x) => { x.disabled = true; });
  emc.resp = null;
  fecharEditorDoEmail(true);
  notaDeFeitoNaConversa(feito && feito.resumo ? feito.resumo + "." : (aguardando ? "A resposta está esperando o seu sim em Aprovações." : "Enviei a resposta."));
}

(function () {
  ligarModosDoEmail();
  // Saiu da conversa do e-mail (outra conversa, ou uma nova): a barra e o
  // texto da resposta saem da caixa de pedido. O rascunho fica guardado.
  const col = $("conversa-col");
  if (col && typeof MutationObserver === "function") {
    new MutationObserver(() => {
      if (emc.resp && emc.trabalho !== estado.trabalhoId) fecharEditorDoEmail(true);
      atualizarModosDoEmail();
    }).observe(col, { attributes: true, attributeFilter: ["class"] });
  }
})();
