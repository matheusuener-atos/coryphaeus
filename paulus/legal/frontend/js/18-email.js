/* --------------------------------------------------- e-mail (B1, B2, B3) */
/*
   O E-mail (docs/ui/03-telas-desktop.md, A7). Tres visoes da mesma tela:
   a caixa de entrada (desenhada em js/29-email-caixa.js, uma lista na
   largura da tela, com a mensagem aberta no lugar da linha), Escrever (aqui:
   a carta, os anexos embaixo dela e a coluna "Pedir aqui") e Contas
   (js/28-email-contas.js). Um estado so; a senha nunca volta do servidor:
   quando falta, a tela pede. E nada sai daqui sem passar pela fila de
   aprovacao - e-mail enviado nao volta.
*/

const mail = {
  contas: null, conta: null,
  caixa: null, aberta: null, filtro: "tudo", busca: "",
  rascunho: null, anexos: [],
  visao: "caixa", pasta: "entrada", erroCaixa: "",
  envios: [], envioAberto: null, fila: [], pedidoAberto: null,
  para: [], inicio: null, conversa: [], cadastros: null, preparando: false,
  reconectar: null, auto: true, padrao: false, guardar: true, prova: null,
  modelo: null, pedindo: "", sugestao: null,
};

/* ------------------------------------------------------- entradas */

async function mostrarEmail(visao) {
  abrirTela("E-mail", { cheia: true });
  marcarDestino("caixa");
  if (visao) mail.visao = visao;

  const centro = $("centro");
  centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  try {
    mail.contas = await (await fetch("/api/email/contas")).json();
  } catch (err) {
    centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' + esc(String(err)) + "</p></div></div>";
    return;
  }
  const contas = mail.contas.contas;
  if (!contas.length) mail.visao = "contas";
  if (!mail.conta || !contas.some((c) => c.id === mail.conta.id)) {
    mail.conta = contas.find((c) => c.em_uso) || contas[0] || null;
  }
  if (mail.visao === "caixa") {
    await carregarPasta();
    carregarFilaDeEmail().then(() => { const n = document.querySelector('[data-em-pasta="aprovacao"] .em-conta'); if (n) n.textContent = mail.fila.length || ""; });
  }
  if (mail.visao === "novo") prepararComposicao();
  desenharEmail();
  atualizarPostura();
}

function telaContas() { return mostrarEmail("contas"); }
function carregarCaixa() { mail.pasta = "entrada"; mail.aberta = null; return mostrarEmail("caixa"); }

/* Quem chama de fora (Agenda, Documentos) passa para/assunto/corpo; os
   anexos podem ser postos logo depois, antes de a tela desenhar. */
function telaEscrever(inicio) {
  mail.inicio = inicio || null;
  mail.anexos = (inicio && inicio.anexos) || [];
  mail.conversa = [];
  return mostrarEmail("novo");
}

function prepararComposicao() {
  const i = mail.inicio;
  const local = i ? null : lerRascunhoLocal();
  const base = i || local || {};
  mail.para = enderecosDe(base.para);
  mail.cc = base.cc || "";
  mail.cco = base.cco || "";
  mail.assunto = base.assunto || "";
  mail.corpo = base.corpo || "";
  if (local && local.anexos && !mail.anexos.length) mail.anexos = local.anexos;
  mail.salvoEm = local ? local.quando : "";
  mail.inicio = null;
  mail.sugestao = null;
}

function enderecosDe(texto) {
  return String(texto || "").split(/[,;]/).map((x) => x.trim()).filter(Boolean);
}

/* ---------------------------------------------------------- dados */

async function carregarPasta() {
  mail.erroCaixa = "";
  if (mail.pasta === "entrada") {
    if (!mail.conta) { mail.caixa = null; return; }
    const busca = mail.busca ? "&busca=" + encodeURIComponent(mail.busca) : "";
    const r = await fetch("/api/email/caixa?filtro=" + mail.filtro + busca + "&conta_id=" + mail.conta.id);
    if (!r.ok) { mail.erroCaixa = await erroDe(r); mail.caixa = null; return; }
    mail.caixa = await r.json();
    return;
  }
  if (mail.pasta === "enviados") {
    try { mail.envios = (await (await fetch("/api/email/envios")).json()).envios || []; } catch (err) { mail.envios = []; }
  } else if (mail.pasta === "aprovacao") {
    await carregarFilaDeEmail();
  }
}

async function carregarFilaDeEmail() {
  try {
    const d = await (await fetch("/api/aprovacoes")).json();
    mail.fila = (d.pendentes || []).filter((p) => p.categoria === "email");
  } catch (err) { mail.fila = []; }
}

function lerRascunhoLocal() {
  try { return JSON.parse(localStorage.getItem("paulus.email.rascunho") || "null"); } catch (err) { return null; }
}

function gravarRascunhoLocal() {
  const campo = $("nm-corpo");
  if (!campo) return;
  const d = {
    para: mail.para.join(", "), cc: ($("nm-cc") || {}).value || "", cco: ($("nm-cco") || {}).value || "",
    assunto: $("nm-assunto").value, corpo: campo.value, anexos: mail.anexos,
    quando: new Date().toISOString(),
  };
  if (!d.para && !d.assunto && !d.corpo.trim() && !d.anexos.length) { apagarRascunhoLocal(); return; }
  try { localStorage.setItem("paulus.email.rascunho", JSON.stringify(d)); } catch (err) { return; }
  mail.salvoEm = d.quando;
  const selo = $("nm-salvo");
  if (selo) selo.textContent = "Rascunho salvo às " + d.quando.slice(11, 16);
}

function apagarRascunhoLocal() {
  try { localStorage.removeItem("paulus.email.rascunho"); } catch (err) { /* sem armazenamento */ }
  mail.salvoEm = "";
}

/* --------------------------------------------------------- a tela */

/* A caixa e a Contas trocam este desenho (js/29 e js/28); aqui fica o
   Escrever e, por baixo, a Contas antiga. */
function desenharEmail() {
  cabecalhoEmail();
  let principal, painel;
  if (mail.visao === "contas") { principal = cartaoDeContas(); painel = painelDeContas(); }
  else { principal = cartaoDeEscrever(); painel = painelDeEscrever(); }
  $("centro").innerHTML = '<div class="acervo em-corpo" id="email"><div class="acervo-principal em-principal">' + principal + "</div>" + painel + "</div>";
  ligarEmail();
}

function cabecalhoEmail() {
  const c = mail.conta;
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  const sinc = c
    ? (c.ultimo_erro
        ? '<span class="docs-sinc atencao"><i></i>senha recusada</span>'
        : (c.quando_ok ? '<span class="docs-sinc"><i></i>sincronizado ' + esc(c.quando_ok) + "</span>" : ""))
    : "";
  if (mail.visao === "contas") {
    const n = mail.contas.contas.length;
    const atencao = mail.contas.contas.filter((x) => x.ultimo_erro || !x.tem_senha).length;
    titulo.textContent = "Contas de e-mail";
    meta.textContent = plural(n, "conta") + (atencao ? " · " + atencao + (atencao === 1 ? " precisa" : " precisam") + " de atenção" : "");
  } else if (mail.visao === "ajustes") {
    titulo.textContent = "Configurações do e-mail";
    meta.textContent = "como as mensagens abrem e a assinatura de cada conta";
  } else if (mail.visao === "novo") {
    titulo.textContent = mail.assunto ? "Novo e-mail" : "Novo e-mail";
    meta.innerHTML = "Enviando como " + esc(c ? c.email : "nenhuma conta") +
      ' · <button class="em-ligacao" data-em-visao="contas">trocar conta</button>';
  } else {
    titulo.textContent = "E-mail";
    const k = mail.caixa;
    /* A mesma conta da lista: nao respondida e (nao lida ou com prazo). */
    const pedem = k ? k.mensagens.filter((m) => !m.respondido && (!m.lido || !!m.prazo)).length : 0;
    meta.innerHTML = (k
      ? plural(k.nao_lidos, "não lida") + " · " + pedem + (pedem === 1 ? " pede" : " pedem") + " resposta"
      : (mail.erroCaixa ? "não consegui abrir a caixa" : (c ? "abrindo…" : "nenhuma conta conectada"))) +
      (sinc ? " · " + sinc : "");
  }

  const botao = (v, r) => {
    const classe = v === mail.visao ? "ativa" : "";
    return '<button class="' + classe + '" data-em-visao="' + v + '">' + r + "</button>";
  };
  /* As tres visoes num grupo so e a busca mais curta: em janela estreita o
     botao de acao sai (a visao Escrever faz o mesmo) e o titulo nao quebra. */
  $("acoes-tela").innerHTML =
    '<label class="busca-tela em-busca">' + ic("search", 18) + '<input type="text" id="mail-busca" placeholder="Buscar e-mails…" value="' + esc(mail.busca) + '"></label>' +
    '<div class="visoes">' + botao("caixa", "Caixa de entrada") + botao("novo", "Escrever") + botao("contas", "Contas") + botao("ajustes", "Configurações") + "</div>" +
    (mail.visao === "novo"
      ? '<button class="com-icone em-acao-tela" id="em-voltar">' + ic("arrow_back", 16) + "Voltar à caixa</button>"
      : '<button class="primario com-icone em-acao-tela" id="em-escrever">' + ic("edit", 16) + "Escrever</button>");
  $("nav-tela").innerHTML = "";
}

/* O provedor pelo dominio: a marca ajuda a achar a conta na lista. */
function avatarDaConta(c, grande) {
  const dominio = (c.dominio || (c.email || "").split("@")[1] || "").toLowerCase();
  let tipo = "outro", letra = c.iniciais || (c.email || "?").slice(0, 2).toUpperCase();
  if (/gmail|googlemail/.test(dominio)) { tipo = "gmail"; letra = "M"; }
  else if (/outlook|hotmail|live\.|office365|msn\./.test(dominio)) { tipo = "outlook"; letra = "O"; }
  const classe = "em-avatar " + tipo + (grande ? " grande" : "");
  return '<span class="' + classe + '" title="' + esc(dominio) + '">' + esc(letra) + "</span>";
}

function iniciaisDoRemetente(nome) {
  const pedacos = String(nome || "").replace(/[<>"]/g, "").trim().split(/\s+/).filter(Boolean);
  if (!pedacos.length) return "?";
  return (pedacos[0][0] + (pedacos[1] ? pedacos[1][0] : "")).toUpperCase();
}

function estadoDaConta(c) {
  if (c.ultimo_erro) return { texto: "senha recusada", classe: "acc" };
  if (!c.tem_senha) return { texto: "sem senha guardada", classe: "" };
  if (c.em_uso) return { texto: "em uso" + (c.quando_ok ? " · " + c.quando_ok : ""), classe: "ok" };
  return { texto: c.quando_ok ? "sincronizado " + c.quando_ok : "ainda não sincronizada", classe: "" };
}

/* ------------------------------------ pecas que a caixa (js/29) usa */

function rotuloDoPrazo(prazo) {
  const hoje = new Date();
  const d = new Date(prazo + "T12:00:00");
  const dias = Math.round((d - new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate(), 12)) / 86400000);
  if (dias === 0) return "prazo hoje";
  if (dias === 1) return "prazo amanhã";
  if (dias < 0) return "prazo venceu";
  return "prazo " + dataCurta(prazo);
}

function vazioDaLista(titulo, texto) {
  return '<div class="em-vazio"><h4>' + titulo + "</h4><p>" + texto + "</p></div>";
}

function corpoComPrazo(corpo, trecho) {
  const texto = esc(corpo || "(mensagem sem texto)");
  if (!trecho) return texto;
  const marca = esc(trecho);
  const onde = texto.indexOf(marca);
  if (onde < 0) return texto;
  return texto.slice(0, onde) + '<mark class="em-marca">' + marca + "</mark>" + texto.slice(onde + marca.length);
}

/* --------------------------------------------------- B2: novo e-mail */

function cartaoDeEscrever() {
  const c = mail.conta;
  const contas = mail.contas.contas;
  const chips = mail.para.map((p, i) => '<span class="em-chip">' + esc(p) + '<span class="ic ic-16" data-nm-tirar-para="' + i + '" title="Tirar">close</span></span>').join("");
  return '<div class="em-compor">' +
    '<div class="em-compor-topo"><span class="cresce">Novo e-mail</span><span id="nm-salvo">' +
    (mail.salvoEm ? "Rascunho salvo às " + esc(mail.salvoEm.slice(11, 16)) : "rascunho ainda não salvo") + "</span>" +
    (c ? '<span class="em-conta-chip">' + avatarDaConta(c) + '<select id="nm-conta">' + contas.map((x) =>
      '<option value="' + esc(x.id) + '"' + (x.id === c.id ? " selected" : "") + ">" + esc(x.email) + "</option>").join("") + "</select></span>" : "") + "</div>" +
    '<div class="em-linha"><span class="em-rotulo">Para</span><div class="em-chips" id="nm-para-chips">' + chips +
    '<input type="text" id="nm-para" placeholder="' + (mail.para.length ? "adicionar…" : "nome@dominio.com.br") + '"></div>' +
    '<button class="em-ligacao" id="nm-cc-toggle">CC · CCO</button></div>' +
    '<div class="em-linha" id="nm-linha-cc"' + (mail.cc ? "" : " hidden") + '><span class="em-rotulo">CC</span><input class="em-campo-linha" type="text" id="nm-cc" value="' + esc(mail.cc || "") + '" placeholder="opcional"></div>' +
    '<div class="em-linha" id="nm-linha-cco"' + (mail.cco ? "" : " hidden") + '><span class="em-rotulo">CCO</span><input class="em-campo-linha" type="text" id="nm-cco" value="' + esc(mail.cco || "") + '" placeholder="opcional"></div>' +
    '<div class="em-linha"><span class="em-rotulo">Assunto</span><input class="em-campo-linha assunto" type="text" id="nm-assunto" value="' + esc(mail.assunto || "") + '" placeholder="Assunto"></div>' +
    '<div class="em-compor-corpo">' + faixaDaSugestao() +
    '<textarea class="em-texto' + (mail.sugestao ? " sugerido" : "") + '" id="nm-corpo" placeholder="Escreva aqui…">' + esc(mail.corpo || "") + "</textarea>" +
    (c && c.assinatura ? '<div class="em-assinatura">' + esc(c.assinatura) + "</div>" : "") + "</div>" +
    /* Os anexos moram debaixo da carta, no espaco dela - e o "Anexar" abre o
       modal de sempre (Acervo e Meu computador), nunca a coluna ao lado. */
    '<div class="em-anexos-bloco" id="nm-anexos"></div>' +
    '<div class="em-compor-rodape"><span class="em-msg-acoes"><button id="nm-anexar-2" title="Anexar arquivos" aria-label="Anexar arquivos">' + ic("attach_file", 18) + "</button>" +
    '<button id="nm-previa" title="Ver como vai chegar" aria-label="Ver como vai chegar">' + ic("visibility", 18) + "</button></span>" +
    '<span class="direita"><button class="com-icone" id="nm-descartar">' + ic("delete", 16) + "Descartar</button>" +
    '<button class="com-icone" id="nm-salvar">' + ic("save", 16) + "Salvar rascunho</button>" +
    '<button class="primario com-icone" id="nm-enviar">' + ic("schedule_send", 16) + rotuloDoEnviar() + "</button></span></div></div>";
}

function rotuloDoEnviar() {
  const c = mail.conta;
  return c && c.pode_enviar_sem_confirmar && mail.contas.pode_enviar_sozinho ? "Enviar" : "Enviar para aprovação";
}

/* O texto que o assistente reescreveu fica na carta como sugestao: a faixa
   diz o que foi pedido e deixa manter ou voltar ao texto de antes. Escrever
   por cima tambem conta como manter. */
function faixaDaSugestao() {
  const s = mail.sugestao;
  if (!s) return "";
  return '<div class="em-sugestao" id="nm-sugestao">' + ic("auto_awesome", 16) +
    '<span class="cresce">Texto reescrito pelo assistente · <b>' + esc(s.rotulo) + "</b>. Confira antes de enviar.</span>" +
    '<button class="com-icone" id="nm-sug-descartar">' + ic("undo", 16) + "Voltar ao meu texto</button>" +
    '<button class="primario com-icone" id="nm-sug-manter">' + ic("check", 16) + "Manter</button></div>";
}

/* Os atalhos: os de regra fazem na hora; os do assistente chamam o modelo
   desta maquina (cerca de um minuto) e somem do jeito certo quando ele nao
   esta respondendo. */
const ATALHOS_DO_EMAIL = [
  { id: "formal", rotulo: "Deixar mais formal", modelo: true },
  { id: "resumir", rotulo: "Resumir", modelo: true },
  { id: "telefone", rotulo: "Adicionar o telefone", modelo: false },
  { id: "contato", rotulo: "Copiar a outra conta", modelo: false },
];

function painelDeEscrever() {
  const m = mail.modelo;
  const fora = m && !m.ok;
  const outra = mail.contas.contas.some((x) => !mail.conta || x.id !== mail.conta.id);
  const chips = ATALHOS_DO_EMAIL.filter((a) => a.id !== "contato" || outra).map((a) => {
    const parado = (a.modelo && (fora || !!mail.pedindo));
    return '<button data-nm-chip="' + a.id + '"' + (parado ? " disabled" : "") + (a.modelo ? ' title="Pelo assistente local · cerca de um minuto"' : "") + ">" +
      (a.modelo ? ic("auto_awesome", 15) : "") + esc(a.rotulo) + "</button>";
  }).join("");
  return '<aside class="acervo-painel em-pedir"><div class="rolagem em-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Pedir aqui</h3><span class="meta">mudanças no texto deste e-mail</span></span></div>' +
    '<div class="em-pedir-corpo"><div class="docs-chips em-atalhos">' + chips + "</div>" +
    '<div class="docs-pedido-linha em-pedido-linha"><input type="text" id="nm-pedido" placeholder="Peça uma mudança no texto…"' + (fora || mail.pedindo ? " disabled" : "") + ">" +
    '<button class="enviar" id="nm-pedir" aria-label="Pedir"' + (fora || mail.pedindo ? " disabled" : "") + ">" + ic("arrow_forward", 18) + "</button></div>" +
    '<div id="nm-andamento">' + andamentoDoPedido() + "</div>" +
    '<div class="docs-conversa em-falas" id="nm-fala">' + falasDoEmail() + "</div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Conferi</span><span class="em-regra">por regra, agora</span></div>' +
    '<div class="em-conferencias" id="nm-conferi">' + conferenciasDoEmail() + "</div></div>" +
    "</div></aside>";
}

/* O estado do assistente, sem prometer: escrevendo (com o anel so enquanto
   escreve), desligado (com o motivo) ou pronto. */
function andamentoDoPedido() {
  const m = mail.modelo;
  if (mail.pedindo) return '<p class="em-andamento ativo">' + coroa(15) + "<span>Escrevendo “" + esc(mail.pedindo) + "”… cerca de um minuto nesta máquina.</span></p>";
  if (!m) return '<p class="em-andamento">Conferindo se o assistente local está respondendo…</p>';
  if (!m.ok) return '<p class="em-andamento fora">' + ic("error", 15) + "<span>O assistente local não está respondendo agora, então “Deixar mais formal”, " +
    "“Resumir” e o pedido livre ficam parados. Os outros atalhos continuam valendo.</span></p>";
  return '<p class="em-andamento">O assistente local reescreve o texto e mostra na carta para você manter ou voltar atrás. Leva cerca de um minuto; nada é enviado por isso.</p>';
}

function falasDoEmail() {
  return mail.conversa.slice(-6).map((m) => m.autor === "pessoa"
    ? '<div class="docs-bolha">' + esc(m.texto) + "</div>"
    : '<div class="docs-resposta' + (m.erro ? " em-fala-erro" : "") + '"><p>' + esc(m.texto) + "</p></div>").join("");
}

function redesenharPedirAqui() {
  const painel = document.querySelector("#email .em-pedir");
  if (!painel || mail.visao !== "novo") return;
  const rolagem = painel.querySelector(".rolagem");
  const topo = rolagem ? rolagem.scrollTop : 0;
  painel.outerHTML = painelDeEscrever();
  const novo = document.querySelector("#email .em-pedir .rolagem");
  if (novo) novo.scrollTop = topo;
  ligarPedirAqui();
}

/* As conferencias sao feitas aqui, com o que esta na tela: destinatario no
   cadastro, anexo citado sem arquivo, valores e datas no texto, a conta. */
function conferenciasDoEmail() {
  const c = mail.conta;
  const corpo = ($("nm-corpo") ? $("nm-corpo").value : mail.corpo) || "";
  const assunto = ($("nm-assunto") ? $("nm-assunto").value : mail.assunto) || "";
  const itens = [];
  const linha = (grau, texto) => {
    const classe = "em-conferencia " + grau;
    return '<div class="' + classe + '">' + ic(grau === "ok" ? "check_circle" : "error", 18) + "<span>" + texto + "</span></div>";
  };
  if (!mail.para.length) itens.push(linha("aviso", "Falta o destinatário."));
  else if (mail.cadastros) {
    mail.para.forEach((p) => {
      const f = mail.cadastros.find((x) => (x.email || "").trim().toLowerCase() === p.toLowerCase());
      itens.push(f ? linha("ok", "Destinatário está no cadastro · " + esc(f.nome)) : linha("aviso", esc(p) + " não está no cadastro."));
    });
  }
  if (!assunto.trim()) itens.push(linha("aviso", "Sem assunto — quem recebe não sabe do que se trata."));
  const citaAnexo = /\banex[oa]/i.test(corpo);
  const grandes = mail.anexos.filter((a) => a.grande);
  if (grandes.length) itens.push(linha("aviso", esc(grandes.map((a) => a.nome).join(", ")) + " passa do limite de 20 MB por anexo."));
  if (mail.anexos.length) itens.push(linha("ok", plural(mail.anexos.length, "anexo") + " · o destinatário recebe o arquivo inteiro"));
  else if (citaAnexo) itens.push(linha("aviso", "O texto cita anexo, mas nenhum arquivo foi anexado."));
  const valores = corpo.match(/R\$\s?[\d.]+(,\d{2})?/g);
  if (valores) itens.push(linha("ok", "Cita " + plural(valores.length, "valor", "valores") + ": " + esc(valores.slice(0, 3).join(", ")) + " — confira antes de enviar."));
  const datas = corpo.match(/\b\d{1,2}\/\d{1,2}(\/\d{2,4})?\b/g);
  if (datas) itens.push(linha("ok", "Cita " + plural(datas.length, "data") + ": " + esc(datas.slice(0, 3).join(", "))));
  if (c && c.ultimo_erro) itens.push(linha("aviso", "A conta " + esc(c.email) + " está com a senha recusada — reconecte antes de enviar."));
  else if (c) itens.push(linha("ok", "Sai por " + esc(c.email) + (c.pode_enviar_sem_confirmar && mail.contas.pode_enviar_sozinho ? "" : " · passa por Aprovações")));
  return itens.join("") || "<p>Nada a apontar por enquanto.</p>";
}

function atualizarConferencias() {
  const alvo = $("nm-conferi");
  if (alvo) alvo.innerHTML = conferenciasDoEmail();
}

/* ------------------------------------------------- B1: contas de e-mail */

function cartaoDeContas() {
  const contas = mail.contas.contas;
  const linhas = contas.map((c) => {
    const e = estadoDaConta(c);
    const classe = "em-conta-linha" + (c.em_uso ? " ativa" : "") + (c.ultimo_erro ? " problema" : "");
    const meta = c.ultimo_erro
      ? '<small class="em-estado acc">Senha recusada · entre de novo</small>'
      : "<small>" + esc(c.resumo_servidor || "") + " · " + esc(c.quando_ok ? "sincronizado " + c.quando_ok : (c.tem_senha ? "ainda não sincronizada" : "sem senha guardada")) + "</small>";
    return '<div class="' + classe + '" data-em-conta-linha="' + esc(c.id) + '">' + avatarDaConta(c, true) +
      '<span class="duas-linhas"><b>' + esc(c.email) + "</b>" + meta + "</span>" +
      (c.em_uso ? '<span class="em-pilula ok">padrão de envio</span>' : '<button data-em-usar="' + esc(c.id) + '">Usar como padrão</button>') +
      (c.ultimo_erro || !c.tem_senha ? '<button class="com-icone" data-em-reconectar="' + esc(c.id) + '">' + ic("sync", 16) + "Reconectar</button>" : "") +
      '<button class="mais-linha" data-em-mais-conta="' + esc(c.id) + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");
  const alguma = contas.some((c) => c.tem_senha);
  return '<div class="em-contas"><div class="em-contas-topo"><span class="cresce">Contas conectadas</span><span>' +
    plural(contas.length, "conta") + " · a primeira envia por padrão</span></div>" +
    '<div class="em-rolagem">' + (linhas || vazioDaLista("Nenhuma conta ainda", "Entre com a sua conta no painel ao lado. A senha fica nesta máquina.")) +
    '<div class="em-contas-rodape"><button class="em-ligacao forte" id="em-conectar">+ conectar outra conta</button>' +
    (alguma ? '<button class="em-ligacao" id="mail-esquecer">apagar todas as senhas</button>' : "") +
    '<span class="cresce"></span><span class="em-nota">Você entra com sua conta · a senha fica nesta máquina</span></div></div>' +
    '<div class="em-como"><span class="em-como-titulo">Como o assistente trata o e-mail</span><div class="em-como-cards">' +
    '<div class="em-como-card"><b>Leio só o que você abre</b><span>Nenhuma mensagem é analisada sem você abrir.</span></div>' +
    '<div class="em-como-card"><b>Prazos vão para a Agenda</b><span>Datas encontradas no texto viram sugestão, nunca compromisso direto.</span></div>' +
    '<div class="em-como-card"><b>Enviar exige aprovação</b><span>Todo envio passa pela tela de Aprovações.</span></div></div></div></div>';
}

function painelDeContas() {
  const r = mail.reconectar;
  const d = mail.contas;
  const classeAuto = "ag-toggle" + (mail.auto ? " on" : "");
  const classePadrao = "ag-toggle" + (mail.padrao ? " on" : "");
  const classeGuardar = "ag-toggle" + (mail.guardar ? " on" : "");
  return '<aside class="acervo-painel"><div class="rolagem em-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + (r ? "Entrar de novo" : "Entrar em uma conta") + '</h3><span class="meta">' +
    (r ? esc(r.email) : "Detecto o servidor pelo domínio") + "</span></span>" +
    (r ? '<button class="voltar" id="mail-cancelar-reconectar" title="Conta nova" aria-label="Conta nova">' + ic("close", 18) + "</button>" : "") + "</div>" +
    '<div class="em-form">' +
    '<div class="ag-campo"><label>Endereço de e-mail</label><input type="text" id="mail-endereco" value="' + esc(r ? r.email : "") + '" placeholder="nome@dominio.com.br"' + (r ? " readonly" : "") + "></div>" +
    '<div class="ag-campo"><div class="em-rotulo-linha"><label>Senha ou senha de app</label><button class="em-ligacao acc" id="mail-como-gerar">como gerar</button></div>' +
    '<div class="em-senha"><input type="password" id="mail-senha" placeholder="••••••••"><button class="em-ligacao" id="mail-mostrar">mostrar</button></div></div>' +
    (r ? "" : '<div class="ag-campo"><label>Seu nome, como aparece para quem recebe</label><input type="text" id="mail-nome" placeholder="Nome e sobrenome"></div>') +
    '<div id="mail-ajuda"></div>' +
    (r ? "" :
      '<div class="' + classeAuto + '" data-mail-toggle="auto"><span>Detectar servidor automaticamente</span><i></i></div>' +
      '<div class="em-servidores" id="mail-servidores">' +
      '<div class="ag-duas"><div class="ag-campo"><label>IMAP</label><input type="text" id="mail-imap" placeholder="imap.dominio.com.br"></div>' +
      '<div class="ag-campo"><label>porta</label><input type="text" id="mail-imap-porta" value="993"></div></div>' +
      '<div class="ag-duas"><div class="ag-campo"><label>SMTP</label><input type="text" id="mail-smtp" placeholder="smtp.dominio.com.br"></div>' +
      '<div class="ag-campo"><label>porta</label><input type="text" id="mail-smtp-porta" value="587"></div></div></div>' +
      '<div class="' + classePadrao + '" data-mail-toggle="padrao"><span>Usar como conta padrão de envio</span><i></i></div>' +
      (d.pode_guardar_senha
        ? '<div class="' + classeGuardar + '" data-mail-toggle="guardar"><span>Guardar a senha nesta máquina</span><i></i></div>'
        : '<p class="ag-explica">Não consigo guardar senha com segurança neste sistema: vou perguntar quando precisar.</p>') +
      '<div class="ag-campo"><label>Assinatura de rodapé</label><textarea id="mail-assinatura" placeholder="Nome · OAB/UF 00000"></textarea></div>') +
    '<div id="mail-prova"></div>' +
    '<div class="ag-form-rodape"><span class="ag-explica">A senha é guardada no cofre desta máquina e não sai dela.</span>' +
    '<button id="mail-testar">Testar</button><button class="primario com-icone" id="mail-entrar">' + ic("login", 16) + "Entrar</button></div>" +
    "</div></div></aside>";
}

/* -------------------------------------------------------- ligacoes */

function ligarEmail() {
  document.querySelectorAll("[data-em-visao]").forEach((b) => {
    b.onclick = () => (b.dataset.emVisao === "novo" ? telaEscrever() : mostrarEmail(b.dataset.emVisao));
  });
  const busca = $("mail-busca");
  busca.onkeydown = (e) => {
    if (e.key === "Enter") { mail.busca = busca.value.trim(); mail.pasta = "entrada"; mail.aberta = null; mostrarEmail("caixa"); }
    if (e.key === "Escape") { busca.value = ""; if (mail.busca) { mail.busca = ""; mostrarEmail("caixa"); } }
  };
  const escrever = $("em-escrever");
  if (escrever) escrever.onclick = () => telaEscrever();
  const voltar = $("em-voltar");
  if (voltar) voltar.onclick = () => { gravarRascunhoLocal(); mostrarEmail("caixa"); };

  if (mail.visao === "contas") return ligarContas();
  if (mail.visao === "novo") return ligarEscrever();
  if (mail.visao === "ajustes") return ligarAjustesDoEmail();
  ligarCaixa();
}

async function abrirMensagem(uid) {
  const r = await fetch("/api/email/mensagem?uid=" + encodeURIComponent(uid) + (mail.conta ? "&conta_id=" + mail.conta.id : ""));
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  mail.aberta = await r.json();
  const item = (mail.caixa && mail.caixa.mensagens || []).find((m) => m.uid === uid);
  if (item && !item.lido) { item.lido = true; if (mail.caixa.nao_lidos > 0) mail.caixa.nao_lidos -= 1; }
  desenharEmail();
}

/* O prazo do texto vira tarefa com data - sugestao na Agenda, nunca
   compromisso direto. "Criar na Agenda" ainda leva ate o dia. */
async function criarPrazoDoEmail(m, irParaAgenda) {
  const r = await fetch("/api/tarefas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dados: {
      titulo: "Responder: " + (m.assunto || m.de_nome || "e-mail"), prazo: m.prazo,
      anotacao: "De " + (m.de_nome || "") + " <" + m.de_email + ">" + (m.prazo_trecho ? "\n\n" + m.prazo_trecho : ""),
    } }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  if (!irParaAgenda) { avisoCert("tarefa criada para " + dataCurta(m.prazo) + " — aparece na Agenda como prazo"); return; }
  const d = deIso(m.prazo);
  ag.dia = m.prazo;
  ag.mes = new Date(d.getFullYear(), d.getMonth(), 1);
  ag.diaAberto = null;
  mostrarAgenda("mes");
}

/* Envia ou poe na fila; se a senha nao esta na maquina, pergunta uma vez. */
async function mandarPedido(pedido) {
  let r = await fetch("/api/email/enviar", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pedido),
  });
  if (r.status === 401) {
    const senha = await perguntar({ titulo: "Senha da conta de e-mail", contexto: "E-mail", campo: { rotulo: "Senha", tipo: "password", icone: "key", dica: "Fica só nesta máquina, protegida pela sua conta do Windows." }, confirmar: "Enviar" });
    if (!senha) return null;
    r = await fetch("/api/email/enviar", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(Object.assign({ senha: senha }, pedido)),
    });
  }
  if (!r.ok) { avisoCert(await erroDe(r)); return null; }
  return r.json();
}

/* ------------------------------------------------ escrever: ligacoes */

function ligarEscrever() {
  const raiz = $("email");
  const c = mail.conta;
  if (!c) { avisoCert("conecte uma conta antes de escrever"); return; }
  if (!mail.cadastros) {
    fetch("/api/cadastros").then((r) => r.json()).then((d) => { mail.cadastros = d.fichas || []; atualizarConferencias(); }).catch(() => { mail.cadastros = []; });
  }

  const contaSel = $("nm-conta");
  if (contaSel) contaSel.onchange = () => {
    mail.conta = mail.contas.contas.find((x) => x.id === contaSel.value) || mail.conta;
    desenharEmail();
  };

  const campoPara = $("nm-para");
  const adicionarPara = () => {
    enderecosDe(campoPara.value).forEach((p) => { if (!mail.para.includes(p)) mail.para.push(p); });
    campoPara.value = "";
    redesenharPara();
  };
  campoPara.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === "," || e.key === ";" || e.key === "Tab") { if (campoPara.value.trim()) { e.preventDefault(); adicionarPara(); } }
    if (e.key === "Backspace" && !campoPara.value && mail.para.length) { mail.para.pop(); redesenharPara(); }
  };
  campoPara.onblur = () => { if (campoPara.value.trim()) adicionarPara(); };
  raiz.querySelectorAll("[data-nm-tirar-para]").forEach((x) => {
    x.onclick = () => { mail.para.splice(Number(x.dataset.nmTirarPara), 1); redesenharPara(); };
  });
  $("nm-cc-toggle").onclick = () => { $("nm-linha-cc").hidden = false; $("nm-linha-cco").hidden = false; $("nm-cc").focus(); };

  let relogio;
  const mudou = () => { clearTimeout(relogio); relogio = setTimeout(() => { gravarRascunhoLocal(); atualizarConferencias(); }, 800); };
  /* O estado acompanha o que se escreve: trocar a conta redesenha a carta e
     nao pode apagar o assunto ou o texto. */
  [["nm-assunto", "assunto"], ["nm-cc", "cc"], ["nm-cco", "cco"]].forEach(([id, chave]) => {
    const el = $(id);
    if (el) el.oninput = () => { mail[chave] = el.value; mudou(); };
  });
  const corpo = $("nm-corpo");
  corpo.oninput = () => {
    mail.corpo = corpo.value;
    if (mail.sugestao) manterSugestao(true);
    mudou();
  };

  $("nm-anexar-2").onclick = escolherAnexos;
  $("nm-previa").onclick = verPrevia;
  $("nm-salvar").onclick = () => { gravarRascunhoLocal(); avisoCert("rascunho guardado nesta máquina"); };
  $("nm-descartar").onclick = async () => {
    if (($("nm-corpo").value.trim() || mail.para.length) && !(await confirmar({ titulo: "Descartar este e-mail?", contexto: "E-mail › Novo e-mail", texto: "O rascunho some desta máquina.", confirmar: "Descartar", perigo: true }))) return;
    apagarRascunhoLocal();
    mail.anexos = [];
    mail.sugestao = null;
    mostrarEmail("caixa");
  };
  $("nm-enviar").onclick = enviarEmail;
  ligarSugestao();
  ligarPedirAqui();

  desenharAnexos();
  atualizarConferencias();
  if (!mail.modelo) conferirModelo();
  const foco = mail.para.length ? (mail.assunto ? $("nm-corpo") : $("nm-assunto")) : campoPara;
  if (foco) foco.focus();
}

/* O assistente local responde? Pergunta uma vez ao abrir o Escrever; a
   resposta so liga ou desliga os atalhos que dependem dele. */
async function conferirModelo() {
  try {
    const d = await (await fetch("/api/status")).json();
    mail.modelo = { ok: !!d.ollama, mensagem: d.mensagem || "" };
  } catch (err) {
    mail.modelo = { ok: false, mensagem: String(err) };
  }
  redesenharPedirAqui();
}

function ligarPedirAqui() {
  const painel = document.querySelector("#email .em-pedir");
  if (!painel) return;
  painel.querySelectorAll("[data-nm-chip]").forEach((b) => { b.onclick = () => atalhoDoEmail(b.dataset.nmChip); });
  const campo = $("nm-pedido");
  const pedir = () => { const t = campo.value.trim(); if (!t) return; campo.value = ""; pedirNoEmail(t, t); };
  $("nm-pedir").onclick = pedir;
  campo.onkeydown = (e) => { if (e.key === "Enter") pedir(); };
}

function ligarSugestao() {
  const manter = $("nm-sug-manter");
  if (manter) manter.onclick = () => manterSugestao(false);
  const voltar = $("nm-sug-descartar");
  if (voltar) voltar.onclick = () => {
    const s = mail.sugestao;
    if (!s) return;
    const corpo = $("nm-corpo");
    corpo.value = s.antes;
    mail.corpo = s.antes;
    mail.sugestao = null;
    tirarFaixaDaSugestao();
    mail.conversa.push({ autor: "paulus", texto: "Voltei ao seu texto." });
    redesenharPedirAqui();
    gravarRascunhoLocal();
    atualizarConferencias();
  };
}

function manterSugestao(escrevendo) {
  mail.sugestao = null;
  tirarFaixaDaSugestao();
  if (!escrevendo) avisoCert("texto mantido", { tom: "ok" });
}

function tirarFaixaDaSugestao() {
  const faixa = $("nm-sugestao");
  if (faixa) faixa.remove();
  const corpo = $("nm-corpo");
  if (corpo) corpo.classList.remove("sugerido");
}

function redesenharPara() {
  const caixa = $("nm-para-chips");
  if (!caixa) return;
  const campo = $("nm-para");
  const valor = campo ? campo.value : "";
  caixa.innerHTML = mail.para.map((p, i) => '<span class="em-chip">' + esc(p) + '<span class="ic ic-16" data-nm-tirar-para="' + i + '" title="Tirar">close</span></span>').join("") +
    '<input type="text" id="nm-para" placeholder="' + (mail.para.length ? "adicionar…" : "nome@dominio.com.br") + '">';
  $("nm-para").value = valor;
  gravarRascunhoLocal();
  atualizarConferencias();
  ligarEscrever();
  $("nm-para").focus();
}

/* Telefone e a outra conta saem de regra, na hora. Formal e resumir vao ao
   assistente local (pedirNoEmail). */
function atalhoDoEmail(qual) {
  const corpo = $("nm-corpo");
  if (qual === "telefone") {
    fetch("/api/preferencias").then((r) => r.json()).then((d) => {
      const tel = ((d.preferencias || {}).pessoa || {}).telefone;
      if (!tel) { avisoCert("seu telefone não está em Configurações — preencha lá primeiro"); return; }
      corpo.value = corpo.value.replace(/\s+$/, "") + "\n\nTelefone: " + tel;
      corpo.dispatchEvent(new Event("input"));
      avisoCert("telefone acrescentado no fim");
    }).catch(() => avisoCert("não consegui ler as suas preferências"));
    return;
  }
  if (qual === "contato") {
    const outra = mail.contas.contas.find((x) => !mail.conta || x.id !== mail.conta.id);
    if (!outra) { avisoCert("não há outra conta conectada para copiar"); return; }
    $("nm-linha-cc").hidden = false;
    const cc = $("nm-cc");
    cc.value = cc.value ? cc.value + ", " + outra.email : outra.email;
    cc.dispatchEvent(new Event("input"));
    avisoCert("cópia para " + outra.email);
    return;
  }
  const atalho = ATALHOS_DO_EMAIL.find((a) => a.id === qual);
  if (atalho) pedirNoEmail(qual, atalho.rotulo);
}

/* O pedido vai ao modelo desta maquina e volta como sugestao na carta:
   manter ou voltar ao texto de antes. Enquanto escreve, os pedidos param e
   a coluna diz o que esta acontecendo; se o assistente nao responde, diz
   por que. */
async function pedirNoEmail(pedido, rotulo) {
  if (mail.pedindo) return;
  const corpo = $("nm-corpo");
  if (!corpo) return;
  if ((pedido === "formal" || pedido === "resumir") && !corpo.value.trim()) {
    avisoCert("escreva o texto do e-mail antes — não há o que reescrever");
    return;
  }
  const antes = corpo.value;
  mail.pedindo = rotulo;
  mail.conversa.push({ autor: "pessoa", texto: rotulo });
  redesenharPedirAqui();
  corpo.readOnly = true;
  let r = null;
  try {
    r = await fetch("/api/email/reescrever", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pedido: pedido, assunto: ($("nm-assunto") || {}).value || "", corpo: antes }),
    });
  } catch (err) {
    r = null;
    mail.conversa.push({ autor: "paulus", erro: true, texto: "Não consegui falar com o programa: " + err });
  }
  mail.pedindo = "";
  const agora = $("nm-corpo");
  if (agora) agora.readOnly = false;
  if (r && !r.ok) {
    const erro = await erroDe(r);
    if (r.status === 503) mail.modelo = { ok: false, mensagem: erro };
    mail.conversa.push({ autor: "paulus", erro: true, texto: (r.status === 503 ? "O assistente local não respondeu: " : "Não consegui: ") + erro });
  } else if (r) {
    const d = await r.json();
    if (mail.visao === "novo" && agora) {
      mail.sugestao = { antes: antes, rotulo: rotulo };
      agora.value = d.sugestao;
      mail.corpo = d.sugestao;
      const velha = $("nm-sugestao");
      if (velha) velha.remove();
      agora.insertAdjacentHTML("beforebegin", faixaDaSugestao());
      agora.classList.add("sugerido");
      ligarSugestao();
      gravarRascunhoLocal();
      atualizarConferencias();
      mail.conversa.push({ autor: "paulus", texto: "Reescrevi na carta. Confira e mantenha, ou volte ao seu texto." });
    }
  }
  redesenharPedirAqui();
}

function pedidoDoEnvio() {
  const c = mail.conta || mail.contas.contas[0];
  const solto = $("nm-para") ? enderecosDe($("nm-para").value) : [];
  return {
    conta_id: c ? c.id : "",
    para: mail.para.concat(solto.filter((p) => !mail.para.includes(p))).join(", "),
    cc: $("nm-cc") ? $("nm-cc").value : "",
    cco: $("nm-cco") ? $("nm-cco").value : "",
    assunto: $("nm-assunto").value,
    corpo: $("nm-corpo").value,
    anexos: mail.anexos.map((a) => a.path),
  };
}

/* Anexar abre o modal de sempre (03-assistente.js): Acervo ou Meu
   computador. Os arquivos vao pelo caminho, sem copia para o Acervo; o
   servidor confere nome, tamanho e o limite de 20 MB. */
function escolherAnexos() {
  abrirAnexar({
    titulo: "Anexar ao e-mail", contexto: "E-mail › Novo e-mail", verbo: "Anexar",
    aoCaminhos: (caminhos) => acrescentarAnexos(caminhos),
  });
}

async function acrescentarAnexos(caminhos) {
  const novos = (caminhos || []).filter((c) => !mail.anexos.some((a) => a.path === c));
  if (!novos.length) return;
  let achados = novos.map((c) => ({ path: c, nome: c.split(/[\\/]/).pop(), mb: 0 }));
  try {
    const r = await fetch("/api/email/anexos/conferir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminhos: novos }) });
    if (r.ok) achados = (await r.json()).anexos.filter((a) => a.existe);
  } catch (err) { /* sem a conferencia, vai o nome; o envio confere de novo */ }
  mail.anexos = mail.anexos.concat(achados);
  desenharAnexos();
  gravarRascunhoLocal();
  atualizarConferencias();
  if (achados.some((a) => a.grande)) avisoCert("um dos arquivos passa de 20 MB — o servidor de e-mail costuma recusar", { tom: "erro" });
}

function tamanhoDoAnexo(a) {
  const mb = Number(a.mb) || 0;
  if (!mb) return "";
  return mb < 1 ? Math.max(1, Math.round(mb * 1024)) + " KB" : mb.toFixed(1).replace(".", ",") + " MB";
}

/* O espaco dos anexos, debaixo da carta: fichas com nome, tamanho e tirar;
   sem nenhum, um convite que abre o mesmo modal. */
function desenharAnexos() {
  const alvo = $("nm-anexos");
  if (!alvo) return;
  const soma = mail.anexos.reduce((s, a) => s + (Number(a.mb) || 0), 0);
  if (!mail.anexos.length) {
    alvo.innerHTML = '<button class="em-anexar-vazio" id="nm-anexar">' + ic("attach_file", 16) +
      "<span>Anexar arquivos</span><small>do Acervo ou do computador</small></button>";
  } else {
    alvo.innerHTML = '<div class="em-anexos-cabeca"><span>' + plural(mail.anexos.length, "anexo") + (soma ? " · " + tamanhoDoAnexo({ mb: soma }) : "") + "</span>" +
      '<span class="cresce"></span><button class="sv-ligacao" id="nm-anexar">' + ic("attach_file", 15) + "Anexar mais</button></div>" +
      '<div class="em-anexo-fichas">' + mail.anexos.map((a, i) =>
        '<span class="em-anexo-ficha' + (a.grande ? " grande" : "") + '" title="' + esc(a.path || a.nome) + '">' + glifo(a.nome) +
        '<span class="corta">' + esc(a.nome) + "</span>" + (tamanhoDoAnexo(a) ? "<small>" + tamanhoDoAnexo(a) + "</small>" : "") +
        '<button data-tira="' + i + '" title="Tirar este anexo" aria-label="Tirar este anexo">' + ic("close", 15) + "</button></span>").join("") + "</div>";
  }
  $("nm-anexar").onclick = escolherAnexos;
  alvo.querySelectorAll("[data-tira]").forEach((b) => {
    b.onclick = () => { mail.anexos.splice(Number(b.dataset.tira), 1); desenharAnexos(); gravarRascunhoLocal(); atualizarConferencias(); };
  });
  /* Anexo posto de fora (a Assinatura) chega sem tamanho: confere uma vez. */
  const semTamanho = mail.anexos.filter((a) => !a.mb && !a.conferido && a.path);
  if (semTamanho.length) {
    semTamanho.forEach((a) => { a.conferido = true; });
    fetch("/api/email/anexos/conferir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminhos: semTamanho.map((a) => a.path) }) })
      .then((r) => (r.ok ? r.json() : null)).then((d) => {
        if (!d) return;
        d.anexos.forEach((x) => { const a = mail.anexos.find((y) => y.path === x.path); if (a) Object.assign(a, { mb: x.mb, grande: x.grande, conferido: true }); });
        desenharAnexos();
      }).catch(() => {});
  }
}

/* "Ver como vai chegar" num dialogo: de, para, assunto, o texto com a
   assinatura e os anexos, montados pelo servidor sem nada ter saido. */
async function verPrevia() {
  const r = await fetch("/api/email/previa", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pedidoDoEnvio()),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  const ok = await confirmar({
    titulo: "Como vai chegar", contexto: "E-mail › Novo e-mail", classe: "em-previa", larga: true,
    html: fichaDoDialogo([["De", d.de], ["Para", d.para.join(", ")], d.cc.length ? ["CC", d.cc.join(", ")] : null,
      d.cco.length ? ["CCO", d.cco.join(", ")] : null, ["Assunto", d.assunto]]) +
      '<div class="em-previa-corpo">' + esc(d.corpo) + "</div>" +
      (d.anexos.length ? '<div class="em-anexo-fichas">' + d.anexos.map((a) => '<span class="em-anexo-ficha">' + glifo(a.nome) + '<span class="corta">' + esc(a.nome) +
        "</span><small>" + String(a.kb).replace(".", ",") + " KB</small></span>").join("") + "</div>" : "") +
      '<p class="em-previa-resumo">' + esc(d.resumo || "") + "</p>",
    cancelar: "Voltar ao texto", confirmar: rotuloDoEnviar(),
  });
  if (ok) enviarEmail();
}

async function enviarEmail() {
  const botao = $("nm-enviar");
  const pedido = pedidoDoEnvio();
  if (!enderecosDe(pedido.para).length) { avisoCert("informe para quem vai o e-mail"); $("nm-para").focus(); return; }
  botao.disabled = true;
  const antes = botao.innerHTML;
  botao.textContent = "enviando…";
  const d = await mandarPedido(pedido);
  botao.disabled = false;
  botao.innerHTML = antes;
  if (!d) return;
  apagarRascunhoLocal();
  mail.anexos = [];
  mail.sugestao = null;
  mail.corpo = "";
  mail.assunto = "";
  depoisDoEnvio(d, pedido);
}

function depoisDoEnvio(d, enviado) {
  const caixa = document.querySelector(".em-compor");
  if (!caixa) return;
  if (d.aguardando_aprovacao) {
    const e = enviado || {};
    const conta = mail.contas.contas.find((c) => c.id === e.conta_id);
    const n = (e.anexos || []).length;
    const linhas = [["Para", e.para], ["Assunto", e.assunto || "(sem assunto)"], ["Sai por", conta && conta.email],
      n ? ["Anexos", plural(n, "arquivo")] : null].filter((l) => l && l[1]);
    caixa.innerHTML = '<div class="em-espera"><h4>' + ic("schedule_send", 18) + "Aguardando a sua aprovação</h4>" +
      "<p>Nada foi enviado. O e-mail só sai depois que você aprovar em Aprovações.</p>" +
      (linhas.length ? '<dl class="em-espera-ficha">' + linhas.map((l) => "<dt>" + l[0] + "</dt><dd>" + esc(l[1]) + "</dd>").join("") + "</dl>" : "") +
      '<div class="em-vazio-acao"><button class="primario com-icone" id="nm-fila">' + ic("verified", 16) + "Ir para Aprovações</button>" +
      '<button id="nm-outro">Escrever outro</button></div></div>';
    $("nm-fila").onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
  } else {
    caixa.innerHTML = '<div class="em-vazio grande"><h4>Enviado</h4><p>' + esc(d.assunto || "(sem assunto)") + " saiu pelo servidor da sua conta para " +
      esc((d.para || []).join(", ")) + ((d.anexos || []).length ? ", com " + plural(d.anexos.length, "anexo") : "") + ".</p>" +
      '<div class="em-vazio-acao"><button class="primario" id="nm-outro">Escrever outro</button><button id="nm-ver-caixa">Caixa de entrada</button></div></div>';
    $("nm-ver-caixa").onclick = () => carregarCaixa();
  }
  $("nm-outro").onclick = () => telaEscrever();
  carregarFilaDeEmail();
}

/* -------------------------------------------------- contas: ligacoes */

function ligarContas() {
  const raiz = $("email");
  raiz.querySelectorAll("[data-em-usar]").forEach((b) => {
    b.onclick = async () => {
      mail.contas = await (await fetch("/api/email/contas/" + b.dataset.emUsar + "/usar", { method: "POST" })).json();
      mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.conta;
      desenharEmail();
    };
  });
  raiz.querySelectorAll("[data-em-reconectar]").forEach((b) => {
    b.onclick = () => { mail.reconectar = mail.contas.contas.find((c) => c.id === b.dataset.emReconectar) || null; desenharEmail(); $("mail-senha").focus(); };
  });
  raiz.querySelectorAll("[data-em-mais-conta]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const c = mail.contas.contas.find((x) => x.id === b.dataset.emMaisConta);
      if (!c) return;
      menuNaLinha(b, [
        { icone: "sync", rotulo: "Reconectar", acao: () => { mail.reconectar = c; desenharEmail(); $("mail-senha").focus(); } },
        { icone: "inbox", rotulo: "Abrir a caixa desta conta", acao: () => { mail.conta = c; carregarCaixa(); } },
        "-",
        { icone: "delete", rotulo: "Remover", perigo: true, acao: async () => {
          if (!(await confirmar({ titulo: "Remover esta conta?", contexto: "E-mail › Contas › " + c.email, texto: "A senha guardada é apagada. As mensagens continuam no seu servidor.", confirmar: "Remover", perigo: true }))) return;
          mail.contas = await (await fetch("/api/email/contas/" + c.id, { method: "DELETE" })).json();
          mail.conta = mail.contas.contas.find((x) => x.em_uso) || mail.contas.contas[0] || null;
          desenharEmail();
        } },
      ]);
    };
  });
  const esquecer = $("mail-esquecer");
  if (esquecer) esquecer.onclick = async () => {
    if (!(await confirmar({ titulo: "Apagar todas as senhas guardadas?", contexto: "E-mail › Contas", texto: "As contas continuam cadastradas; eu vou perguntar a senha quando precisar.", confirmar: "Apagar senhas", perigo: true }))) return;
    mail.contas = await (await fetch("/api/email/esquecer-senhas", { method: "POST" })).json();
    desenharEmail();
  };
  const conectar = $("em-conectar");
  if (conectar) conectar.onclick = () => { mail.reconectar = null; desenharEmail(); $("mail-endereco").focus(); };
  const cancelar = $("mail-cancelar-reconectar");
  if (cancelar) cancelar.onclick = () => { mail.reconectar = null; desenharEmail(); };

  const senha = $("mail-senha");
  $("mail-mostrar").onclick = () => {
    senha.type = senha.type === "password" ? "text" : "password";
    $("mail-mostrar").textContent = senha.type === "password" ? "mostrar" : "esconder";
  };
  raiz.querySelectorAll("[data-mail-toggle]").forEach((t) => {
    t.onclick = () => {
      const chave = t.dataset.mailToggle;
      mail[chave] = !mail[chave];
      t.classList.toggle("on", mail[chave]);
      if (chave === "auto") { $("mail-servidores").classList.toggle("manual", !mail.auto); if (mail.auto) detectarServidor(); }
    };
  });
  const servidores = $("mail-servidores");
  if (servidores) servidores.classList.toggle("manual", !mail.auto);

  const endereco = $("mail-endereco");
  if (!mail.reconectar) {
    endereco.onchange = () => { if (mail.auto && endereco.value.includes("@")) detectarServidor(); };
    endereco.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); senha.focus(); if (mail.auto) detectarServidor(); } };
  }
  $("mail-como-gerar").onclick = () => detectarServidor(true);
  $("mail-testar").onclick = () => provarConta(false);
  $("mail-entrar").onclick = () => provarConta(true);
  senha.onkeydown = (e) => { if (e.key === "Enter") provarConta(true); };
}

async function detectarServidor(soAjuda) {
  const endereco = $("mail-endereco").value.trim();
  const ajuda = $("mail-ajuda");
  if (!endereco || !endereco.includes("@")) { ajuda.innerHTML = '<p class="ag-explica">informe o e-mail primeiro</p>'; return; }
  mail.detectando = true;
  ajuda.innerHTML = '<p class="nota">procurando o servidor…</p>';
  let d;
  try {
    d = await (await fetch("/api/email/detectar", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: endereco }),
    })).json();
  } catch (err) {
    d = { achou: false, motivo: String(err) };
  }
  mail.detectando = false;
  if (d.achou && $("mail-imap") && !soAjuda) {
    $("mail-imap").value = d.imap_host;
    $("mail-imap-porta").value = d.imap_porta;
    $("mail-smtp").value = d.smtp_host;
    $("mail-smtp-porta").value = d.smtp_porta;
  }
  let texto = "";
  if (d.aviso) texto += '<div class="em-aviso-caixa"><b>Esta conta não vai funcionar aqui</b><p>' + esc(d.aviso) + "</p></div>";
  else if (d.ajuda) texto += '<div class="em-aviso-caixa"><b>Como gerar a senha de app</b><p>' + esc(d.ajuda) + "</p></div>";
  if (!soAjuda) {
    texto += '<p class="ag-explica">' + (d.achou ? esc(d.como) + (d.parcial ? " — achei só uma das pontas, confira a outra." : "") : esc(d.motivo || "não achei o servidor; preencha IMAP e SMTP à mão")) + "</p>";
    if (!d.achou && $("mail-servidores")) { mail.auto = false; $("mail-servidores").classList.add("manual"); const t = document.querySelector('[data-mail-toggle="auto"]'); if (t) t.classList.remove("on"); }
  }
  ajuda.innerHTML = texto;
}

function fichaDaTela() {
  const r = mail.reconectar;
  if (r) return { id: r.id, email: r.email };
  return {
    email: $("mail-endereco").value.trim(),
    nome: $("mail-nome").value.trim(),
    imap_host: $("mail-imap").value.trim(),
    imap_porta: Number($("mail-imap-porta").value) || 993,
    smtp_host: $("mail-smtp").value.trim(),
    smtp_porta: Number($("mail-smtp-porta").value) || 587,
    guardar_senha: mail.guardar,
    assinatura: $("mail-assinatura").value.trim(),
  };
}

async function provarConta(entrar) {
  const prova = $("mail-prova");
  const senha = $("mail-senha").value;
  if (!senha) { prova.innerHTML = '<p class="ag-explica">informe a senha</p>'; $("mail-senha").focus(); return; }
  if (!mail.reconectar && !$("mail-imap").value.trim()) {
    await detectarServidor();
    if (!$("mail-imap").value.trim()) { prova.innerHTML = '<p class="ag-explica">preencha o servidor IMAP e SMTP</p>'; return; }
  }

  const botao = entrar ? $("mail-entrar") : $("mail-testar");
  const antes = botao.innerHTML;
  botao.disabled = true;
  botao.textContent = "falando com o servidor…";
  let r;
  try {
    r = await (await fetch("/api/email/testar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dados: fichaDaTela(), senha: senha }),
    })).json();
  } catch (err) {
    r = { ok: false, erro_entrada: String(err) };
  }
  botao.disabled = false;
  botao.innerHTML = antes;

  const linha = (ok, texto, erro) => {
    const classe = "em-conferencia " + (ok ? "ok" : "aviso");
    return '<div class="' + classe + '">' + ic(ok ? "check_circle" : "error", 18) + "<span>" + texto + (ok ? " funciona" : ": " + esc(erro || "não")) + "</span></div>";
  };
  prova.innerHTML = '<div class="em-conferencias">' + linha(r.entrada, "ler as mensagens (IMAP)", r.erro_entrada) + linha(r.saida, "enviar (SMTP)", r.erro_saida) + "</div>";

  /* Guardar uma conta que so le, sem dizer, e descobrir o problema na hora de
     mandar o e-mail que importava. */
  if (!entrar || !r.entrada) return;
  if (!r.saida && !(await confirmar({ titulo: "Guardar a conta assim mesmo?", contexto: "E-mail › Contas", texto: "Dá para ler as mensagens, mas não dá para enviar por esta conta.", confirmar: "Guardar assim mesmo" }))) return;

  if (mail.reconectar) {
    const s = await fetch("/api/email/contas/senha", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: mail.reconectar.id, senha: senha }),
    });
    if (!s.ok) { prova.innerHTML += '<p class="ag-explica">' + esc(await erroDe(s)) + "</p>"; return; }
    mail.contas = await s.json();
    mail.reconectar = null;
  } else {
    mail.contas = await (await fetch("/api/email/contas", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dados: fichaDaTela(), senha: senha }),
    })).json();
    if (mail.padrao) {
      const nova = mail.contas.contas.find((c) => c.email === fichaDaTela().email);
      if (nova) mail.contas = await (await fetch("/api/email/contas/" + nova.id + "/usar", { method: "POST" })).json();
    }
  }
  mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.contas.contas[0] || null;
  avisoCert("conta conectada · a senha fica nesta máquina");
  carregarCaixa();
}

