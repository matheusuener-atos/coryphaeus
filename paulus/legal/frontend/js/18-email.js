/* --------------------------------------------------- e-mail (B1, B2, B3) */
/*
   O E-mail do desenho (docs/ui/03-telas-desktop.md, A7): tres colunas na
   caixa - pastas e contas, conversas, mensagem - e o painel de 400 px com o
   que o assistente entendeu, o prazo detectado e o rascunho. Escrever e
   Contas sao visoes da mesma tela. Um estado so; a senha nunca volta do
   servidor: quando falta, a tela pede. E nada sai daqui sem passar pela
   fila de aprovacao - e-mail enviado nao volta.
*/

const mail = {
  contas: null, conta: null,
  caixa: null, aberta: null, filtro: "tudo", busca: "",
  rascunho: null, anexos: [],
  visao: "caixa", pasta: "entrada", largo: false, erroCaixa: "",
  envios: [], envioAberto: null, fila: [], pedidoAberto: null,
  para: [], inicio: null, conversa: [], cadastros: null, preparando: false,
  reconectar: null, auto: true, padrao: false, guardar: true, prova: null,
};

const PASTAS_DE_EMAIL = [
  { id: "entrada", icone: "inbox", rotulo: "Caixa de entrada" },
  { id: "esperando", icone: "mark_email_unread", rotulo: "Esperando resposta" },
  { id: "enviados", icone: "send", rotulo: "Enviados" },
  { id: "rascunhos", icone: "draft", rotulo: "Rascunhos" },
  { id: "aprovacao", icone: "schedule_send", rotulo: "Aguardando aprovação" },
  { id: "arquivados", icone: "archive", rotulo: "Arquivados", adiante: true },
];
const FILTROS_DA_CAIXA = [["tudo", "Tudo"], ["nao_lidos", "Não lidos"], ["com_anexo", "Anexos"], ["de_clientes", "Clientes"]];

/* ------------------------------------------------------- entradas */

async function mostrarEmail(visao) {
  abrirTela("E-mail", { cheia: true });
  marcarDestino("caixa");
  if (visao) mail.visao = visao;

  const centro = $("centro");
  centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">abrindo…</p></div></div>';
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
}

function enderecosDe(texto) {
  return String(texto || "").split(/[,;]/).map((x) => x.trim()).filter(Boolean);
}

/* ---------------------------------------------------------- dados */

async function carregarPasta() {
  mail.erroCaixa = "";
  if (mail.pasta === "entrada" || mail.pasta === "esperando") {
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

function desenharEmail() {
  cabecalhoEmail();
  let principal, painel;
  if (mail.visao === "contas") { principal = cartaoDeContas(); painel = painelDeContas(); }
  else if (mail.visao === "novo") { principal = cartaoDeEscrever(); painel = painelDeEscrever(); }
  else { principal = colunasDaCaixa(); painel = painelDaCaixa(); }
  const classe = "acervo em-corpo" + (mail.largo ? " painel-largo" : "");
  $("centro").innerHTML = '<div class="' + classe + '" id="email"><div class="acervo-principal em-principal">' + principal + "</div>" + painel + "</div>";
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
  } else if (mail.visao === "novo") {
    titulo.textContent = mail.assunto ? "Novo e-mail" : "Novo e-mail";
    meta.innerHTML = "Enviando como " + esc(c ? c.email : "nenhuma conta") +
      ' · <button class="em-ligacao" data-em-visao="contas">trocar conta</button>';
  } else {
    titulo.textContent = "E-mail";
    const k = mail.caixa;
    meta.innerHTML = (k
      ? plural(k.nao_lidos, "não lido") + " · " + k.sem_resposta + " esperando sua resposta"
      : (mail.erroCaixa ? "não consegui abrir a caixa" : (c ? "abrindo…" : "nenhuma conta conectada"))) +
      (sinc ? " · " + sinc : "");
  }

  const botao = (v, r) => {
    const classe = v === mail.visao ? "ativa" : "";
    return '<button class="' + classe + '" data-em-visao="' + v + '">' + r + "</button>";
  };
  $("acoes-tela").innerHTML =
    '<label class="busca-tela">' + ic("search", 18) + '<input type="text" id="mail-busca" placeholder="Buscar e-mails…" value="' + esc(mail.busca) + '"></label>' +
    '<div class="visoes">' + botao("caixa", "Caixa de entrada") + botao("novo", "Escrever") + "</div>" +
    '<div class="visoes">' + botao("contas", "Contas") + "</div>" +
    (mail.visao === "novo"
      ? '<button class="com-icone" id="em-voltar">' + ic("arrow_back", 16) + "Voltar à caixa</button>"
      : '<button class="primario com-icone" id="em-escrever">' + ic("edit", 16) + "Escrever</button>");
  $("nav-tela").innerHTML = "";
}

function alcaDoEmail() {
  return '<button class="alca-painel" data-em-alca="1" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(mail.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
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

/* ------------------------------------------------ B3: caixa de entrada */

function colunasDaCaixa() {
  return '<div class="em-colunas">' + colunaDePastas() + cartaoDaLista() + cartaoDaMensagem() + "</div>";
}

function contagemDaPasta(id) {
  const k = mail.caixa;
  if (id === "entrada") return k ? k.nao_lidos : 0;
  if (id === "esperando") return k ? k.sem_resposta : 0;
  if (id === "rascunhos") return lerRascunhoLocal() ? 1 : 0;
  if (id === "aprovacao") return mail.fila.length;
  return 0;
}

function colunaDePastas() {
  const pastas = PASTAS_DE_EMAIL.map((p) => {
    const n = contagemDaPasta(p.id);
    const classe = "em-pasta" + (p.id === mail.pasta ? " ativa" : "") + (p.adiante ? " adiante" : "");
    const classeConta = "em-conta" + (n && (p.id === "esperando" || p.id === "aprovacao") ? " acc" : "");
    return '<button class="' + classe + '" data-em-pasta="' + p.id + '">' + ic(p.icone, 18) +
      '<span class="em-nome">' + p.rotulo + '</span><span class="' + classeConta + '">' + (n || "") + "</span></button>";
  }).join("");
  const contas = mail.contas.contas.map((c) => {
    const e = estadoDaConta(c);
    const classe = "em-conta-mini" + (mail.conta && c.id === mail.conta.id ? " ativa" : "");
    const classeEstado = "em-estado " + e.classe;
    return '<button class="' + classe + '" data-em-conta="' + esc(c.id) + '" title="' + esc(c.email) + '">' + avatarDaConta(c) +
      '<span class="duas-linhas"><b>' + esc(c.email) + '</b><small class="' + classeEstado + '">' + esc(e.texto) + "</small></span></button>";
  }).join("");
  return '<div class="em-pastas">' + pastas +
    '<span class="ac-divisa"></span><span class="ac-secao">Contas</span>' + contas +
    '<button class="ac-incluir" data-em-visao="contas">Gerenciar contas →</button></div>';
}

function rotuloDoPrazo(prazo) {
  const hoje = new Date();
  const d = new Date(prazo + "T12:00:00");
  const dias = Math.round((d - new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate(), 12)) / 86400000);
  if (dias === 0) return "prazo hoje";
  if (dias === 1) return "prazo amanhã";
  if (dias < 0) return "prazo venceu";
  return "prazo " + dataCurta(prazo);
}

function linhaDeMensagem(m) {
  const classe = "em-item" + (m.lido ? "" : " nova") + (mail.aberta && mail.aberta.uid === m.uid ? " aberta" : "");
  const sinais = [];
  if (!m.lido && !m.respondido) sinais.push('<span class="em-pilula acc">Responder</span>');
  if (m.prazo) sinais.push('<span class="em-pilula warn">' + esc(rotuloDoPrazo(m.prazo)) + "</span>");
  if (m.tem_anexo) sinais.push("<span>anexo</span>");
  if (m.de_cadastro) sinais.push("<span>cliente</span>");
  return '<div class="' + classe + '" data-em-uid="' + esc(m.uid) + '">' +
    '<div class="em-quem"><b>' + esc(m.de_cadastro || m.de_nome || m.de_email) + "</b><span>" + esc(m.quando_curto) + "</span></div>" +
    '<div class="em-assunto">' + esc(m.assunto || "(sem assunto)") + "</div>" +
    (sinais.length ? '<div class="em-sinais">' + sinais.join("") + "</div>" : "") + "</div>";
}

function cartaoDaLista() {
  const k = mail.caixa;
  const naCaixa = mail.pasta === "entrada" || mail.pasta === "esperando";
  let filtros = "";
  if (naCaixa) {
    filtros = '<div class="em-filtros">' + FILTROS_DA_CAIXA.map(([v, r]) => {
      const classe = "em-filtro" + (v === mail.filtro ? " ativa" : "");
      return '<button class="' + classe + '" data-em-filtro="' + v + '">' + r + "</button>";
    }).join("") + '<span class="em-ordem" title="Mais recentes primeiro">' + ic("swap_vert", 18) + "</span></div>";
  }

  let linhas, rodape = "";
  if (!mail.conta) {
    linhas = vazioDaLista("Nenhuma conta conectada", "Conecte uma conta de e-mail em Contas para ver a caixa de entrada.");
  } else if (naCaixa && mail.erroCaixa) {
    linhas = vazioDaLista("Não consegui abrir", esc(mail.erroCaixa) + " Isso costuma ser senha recusada ou servidor errado; a tela de contas testa as duas pontas.") +
      '<div class="em-vazio-acao"><button class="primario" data-em-visao="contas">Abrir contas</button></div>';
  } else if (naCaixa) {
    const itens = mail.pasta === "esperando" ? k.mensagens.filter((m) => !m.respondido && !m.lido) : k.mensagens;
    linhas = itens.length ? itens.map(linhaDeMensagem).join("") : vazioDaLista("Nada aqui", "Nenhuma mensagem com esse filtro.");
    rodape = "<span>" + (mail.pasta === "esperando" ? itens.length + " esperando" : k.mostrando + " de " + k.total) + '</span><span class="cresce"></span>' +
      (k.tem_mais ? '<button class="em-ligacao forte" id="mail-mais">Carregar mais →</button>' : "");
  } else if (mail.pasta === "enviados") {
    linhas = mail.envios.length
      ? mail.envios.map((e, i) => {
          const classe = "em-item" + (mail.envioAberto === i ? " aberta" : "");
          return '<div class="' + classe + '" data-em-envio="' + i + '"><div class="em-quem"><b>' + esc((e.para || []).join(", ") || "—") + "</b><span>" +
            esc(quandoCurto(e.quando)) + '</span></div><div class="em-assunto">' + esc(e.assunto || "(sem assunto)") + "</div>" +
            ((e.anexos || []).length ? '<div class="em-sinais"><span>' + plural(e.anexos.length, "anexo") + "</span></div>" : "") + "</div>";
        }).join("")
      : vazioDaLista("Nada enviado daqui", "O que sair pelo PAULUS fica anotado aqui; o servidor da sua conta guarda a cópia completa.");
    rodape = "<span>" + plural(mail.envios.length, "envio") + "</span>";
  } else if (mail.pasta === "rascunhos") {
    const r = lerRascunhoLocal();
    linhas = r
      ? '<div class="em-item" data-em-rascunho="1"><div class="em-quem"><b>' + esc(r.para || "sem destinatário") + "</b><span>" + esc(quandoCurto(r.quando)) +
        '</span></div><div class="em-assunto">' + esc(r.assunto || "(sem assunto)") + '</div><div class="em-sinais"><span>rascunho nesta máquina</span></div></div>'
      : vazioDaLista("Nenhum rascunho", "O que você começa a escrever fica guardado aqui, nesta máquina, até sair.");
  } else if (mail.pasta === "aprovacao") {
    linhas = mail.fila.length
      ? mail.fila.map((p) => {
          const classe = "em-item" + (mail.pedidoAberto === p.id ? " aberta" : "");
          return '<div class="' + classe + '" data-em-pedido="' + esc(p.id) + '"><div class="em-quem"><b>' + esc(p.titulo) + "</b><span>" +
            esc(quandoCurto(p.criado_em)) + '</span></div><div class="em-assunto">' + esc(p.resumo || "") + '</div><div class="em-sinais"><span class="em-pilula acc">esperando o seu sim</span></div></div>';
        }).join("")
      : vazioDaLista("Nada esperando", "Todo envio para aqui até você aprovar em Aprovações; agora a fila está vazia.");
  } else {
    linhas = vazioDaLista("Ainda não listo o arquivo", "Arquivar move a mensagem para a pasta de arquivo do seu servidor; ler essa pasta daqui vem adiante.");
  }

  return '<div class="em-lista">' + filtros + '<div class="em-rolagem">' + linhas + "</div>" +
    (rodape ? '<div class="em-lista-rodape">' + rodape + "</div>" : "") + "</div>";
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

function cartaoDaMensagem() {
  const c = mail.conta;
  if (mail.pasta === "enviados" && mail.envioAberto !== null && mail.envios[mail.envioAberto]) {
    const e = mail.envios[mail.envioAberto];
    return '<div class="em-mensagem"><div class="em-msg-cabeca"><span class="em-iniciais">' + esc(iniciaisDoRemetente((e.para || [])[0])) + "</span>" +
      '<span class="duas-linhas"><b class="em-msg-assunto">' + esc(e.assunto || "(sem assunto)") + '</b><small>enviado de ' + esc(e.de) + " · para " +
      esc((e.para || []).join(", ")) + " · " + esc(quandoCurto(e.quando)) + "</small></span></div>" +
      '<div class="em-msg-corpo"><p class="em-explica">O texto completo está na pasta de enviados do seu servidor; aqui fica só o registro de que saiu.</p>' +
      ((e.anexos || []).length ? blocoDeAnexos(e.anexos.map((n) => ({ nome: n })), false) : "") + "</div>" +
      '<div class="em-msg-rodape"><button class="primario com-icone" data-em-escrever-para="' + esc((e.para || []).join(", ")) + '">' + ic("edit", 16) + "Escrever de novo</button></div></div>";
  }
  if (mail.pasta === "aprovacao" && mail.pedidoAberto !== null) {
    const p = mail.fila.find((x) => x.id === mail.pedidoAberto);
    if (p) {
      return '<div class="em-mensagem"><div class="em-msg-cabeca"><span class="em-iniciais">' + ic("schedule_send", 18) + "</span>" +
        '<span class="duas-linhas"><b class="em-msg-assunto">' + esc(p.titulo) + "</b><small>pedido em " + esc(quandoCurto(p.criado_em)) + " · esperando o seu sim</small></span></div>" +
        '<div class="em-msg-corpo"><p>' + esc(p.resumo || "") + "</p>" +
        (p.etiquetas && p.etiquetas.length ? '<div class="em-sinais">' + p.etiquetas.map((t) => '<span class="em-pilula">' + esc(t) + "</span>").join("") + "</div>" : "") + "</div>" +
        '<div class="em-msg-rodape"><button class="primario com-icone" data-em-aprovacoes="1">' + ic("verified", 16) + "Decidir em Aprovações</button>" +
        '<span class="em-nota">O e-mail só sai depois do seu sim.</span></div></div>';
    }
  }
  const m = mail.aberta;
  if (!m) {
    return '<div class="em-mensagem"><div class="em-vazio grande"><h4>Escolha uma mensagem</h4>' +
      "<p>Eu leio a mensagem só quando você abre. Até lá ela fica no seu servidor — por isso a lista abre rápido mesmo com milhares de e-mails.</p></div></div>";
  }
  return '<div class="em-mensagem"><div class="em-msg-cabeca"><span class="em-iniciais">' + esc(iniciaisDoRemetente(m.de_nome || m.de_email)) + "</span>" +
    '<span class="duas-linhas"><b class="em-msg-assunto">' + esc(m.assunto || "(sem assunto)") + "</b><small>" + esc(m.de_nome || "") +
    (m.de_nome ? " · " : "") + esc(m.de_email) + (m.quando_curto ? " · " + esc(m.quando_curto) : "") + (c ? " · para " + esc(c.email.split("@")[0]) + "@" : "") + "</small></span>" +
    '<span class="em-msg-acoes"><button id="mail-responder-ic" title="Responder">' + ic("reply", 18) + "</button>" +
    '<button id="mail-encaminhar" title="Encaminhar">' + ic("forward", 18) + "</button>" +
    '<button id="mail-arquivar" title="Arquivar">' + ic("archive", 18) + "</button>" +
    '<button id="mail-mais-msg" title="Mais">' + ic("more_horiz", 18) + "</button></span></div>" +
    '<div class="em-msg-corpo"><p class="em-texto-msg">' + corpoComPrazo(m.corpo, m.prazo_trecho) + "</p>" +
    (m.anexos && m.anexos.length ? blocoDeAnexos(m.anexos, true) : "") + "</div>" +
    '<div class="em-msg-rodape"><button class="primario com-icone" id="mail-responder">' + ic("reply", 16) + "Responder</button>" +
    (m.pode_rascunhar ? '<button class="com-icone" id="mail-responder-rascunho">' + ic("auto_awesome", 16) + "Responder com o rascunho</button>" : "") +
    '<span class="em-nota">Mensagens ficam no seu servidor · leio só o que você abre</span></div></div>';
}

function blocoDeAnexos(anexos, comAcoes) {
  return '<div class="em-anexos"><span class="em-anexos-cabeca">' + plural(anexos.length, "anexo") + "</span>" +
    anexos.map((a) =>
      '<div class="em-anexo">' + glifo(a.nome || "arquivo") + '<span class="duas-linhas"><b>' + esc(a.nome || "arquivo") + "</b><small>" +
      (a.kb ? String(a.kb).replace(".", ",") + " KB" : "no seu servidor") + "</small></span>" +
      (comAcoes
        ? '<span class="em-msg-acoes"><button data-baixar="' + esc(a.nome) + '" title="Abrir">' + ic("visibility", 18) + "</button>" +
          '<button data-guardar="' + esc(a.nome) + '" title="Guardar no Acervo">' + ic("inventory_2", 18) + "</button></span>"
        : "") + "</div>").join("") + "</div>";
}

function painelDaCaixa() {
  const m = mail.aberta;
  const c = mail.conta;
  if (!m) {
    const k = mail.caixa;
    const pasta = PASTAS_DE_EMAIL.find((p) => p.id === mail.pasta) || PASTAS_DE_EMAIL[0];
    return '<aside class="acervo-painel">' + alcaDoEmail() + '<div class="rolagem em-painel">' +
      '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + pasta.rotulo + '</h3><span class="meta">' + (c ? esc(c.email) : "nenhuma conta") + "</span></span></div>" +
      '<div class="painel-chaves">' +
      '<div class="chave-valor"><span>Não lidos</span><b>' + (k ? k.nao_lidos : "—") + "</b></div>" +
      '<div class="chave-valor"><span>Esperando resposta</span><b>' + (k ? k.sem_resposta : "—") + "</b></div>" +
      '<div class="chave-valor"><span>Aguardando aprovação</span><b>' + mail.fila.length + "</b></div></div>" +
      '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Como trato o e-mail</span></div>' +
      "<p>Leio só o que você abre: nenhuma mensagem é analisada sem isso.</p>" +
      "<p>Prazo achado no texto vira sugestão para a Agenda, nunca compromisso direto.</p>" +
      "<p>Todo envio passa pela tela de Aprovações; nada sai sem o seu sim.</p></div>" +
      "</div></aside>";
  }

  const entendi = esc(m.de_nome || m.de_email) + (m.de_cadastro ? " (" + esc(m.de_cadastro) + ", do cadastro)" : "") +
    " escreveu sobre “" + esc(m.assunto || "sem assunto") + "”." +
    (m.prazo ? " O texto menciona um prazo: “" + esc(m.prazo_trecho || dataBR(m.prazo)) + "”." : "") +
    (m.anexos && m.anexos.length ? " Vem com " + plural(m.anexos.length, "anexo") + "." : "") +
    (m.respondido ? " Você já respondeu." : "");

  let rascunho;
  if (!m.pode_rascunhar) {
    rascunho = "<p>Esta conta não permite que eu escreva rascunhos — dá para mudar em Contas.</p>";
  } else if (mail.preparando) {
    rascunho = '<p class="nota">escrevendo… isso leva cerca de um minuto nesta máquina</p>';
  } else if (mail.rascunho && mail.rascunho.uid === m.uid) {
    rascunho = '<div class="em-rascunho"><b>' + esc(mail.rascunho.assunto) + "</b><p>" + esc(mail.rascunho.rascunho) + "</p></div>" +
      '<div class="em-rascunho-acoes"><button class="em-ligacao" id="mail-abrir-rascunho">Abrir o rascunho</button>' +
      '<button class="primario com-icone" id="mail-aprovar-enviar">' + ic("check", 16) + "Aprovar e enviar</button></div>" +
      '<span class="em-nota">Enviar passa pela tela de Aprovações; nada sai sem o seu sim.</span>';
  } else {
    rascunho = "<p>Posso escrever uma resposta para você revisar. Demora cerca de um minuto nesta máquina, por isso só faço quando você pede.</p>" +
      '<div class="painel-acoes semi"><button class="com-icone" id="mail-preparar">' + ic("auto_awesome", 16) + "Preparar resposta</button></div>";
  }

  return '<aside class="acervo-painel">' + alcaDoEmail() + '<div class="rolagem em-painel">' +
    '<div class="docs-painel-cabeca">' + coroa(18) + '<span class="cresce">O que eu entendi</span><span>lido localmente</span></div>' +
    '<div class="em-entendi"><p>' + entendi + "</p></div>" +
    (m.prazo
      ? '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Prazo detectado</span></div>' +
        '<div class="em-prazo"><span class="data">' + dataCurta(m.prazo) + '</span><span class="duas-linhas"><b>Responder: ' + esc(m.assunto || "sem assunto") + "</b><small>" +
        (m.prazo_trecho ? "“" + esc(m.prazo_trecho) + "”" : dataBR(m.prazo)) + (m.de_cadastro ? " · " + esc(m.de_cadastro) : "") + "</small></span></div>" +
        '<div class="painel-acoes semi"><button class="com-icone" data-em-prazo="agenda">' + ic("event_upcoming", 16) + "Criar na Agenda</button>" +
        '<button class="com-icone" data-em-prazo="tarefa">' + ic("add_task", 16) + "Criar tarefa</button></div></div>"
      : "") +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Rascunho que eu preparei</span>' +
    (mail.rascunho && mail.rascunho.uid === m.uid ? '<span class="contagem ag-acc">esperando você</span>' : "") + "</div>" + rascunho + "</div>" +
    '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Cliente</span><b>' + esc(m.de_cadastro || "não está no cadastro") + "</b></div>" +
    '<div class="chave-valor"><span>Anexos</span><b>' + ((m.anexos || []).length || "nenhum") + "</b></div>" +
    '<div class="chave-valor"><span>Recebido</span><b>' + esc(m.quando_curto || "") + "</b></div></div>" +
    "</div></aside>";
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
    '<div class="em-compor-corpo"><textarea class="em-texto" id="nm-corpo" placeholder="Escreva aqui…">' + esc(mail.corpo || "") + "</textarea>" +
    (c && c.assinatura ? '<div class="em-assinatura">' + esc(c.assinatura) + "</div>" : "") +
    '<div class="em-anexos-bloco"><span class="em-anexos-cabeca"><span id="nm-anexos-n"></span><span class="cresce"></span>' +
    '<button class="em-ligacao forte" id="nm-anexar">Anexar do Acervo</button></span><div id="nm-anexos"></div></div></div>' +
    '<div class="em-compor-rodape"><span class="em-msg-acoes"><button id="nm-anexar-2" title="Anexar do Acervo">' + ic("attach_file", 18) + "</button>" +
    '<button id="nm-previa" title="Ver como vai chegar">' + ic("visibility", 18) + "</button></span>" +
    '<span class="direita"><button class="com-icone" id="nm-descartar">' + ic("delete", 16) + "Descartar</button>" +
    '<button class="com-icone" id="nm-salvar">' + ic("save", 16) + "Salvar rascunho</button>" +
    '<button class="primario com-icone" id="nm-enviar">' + ic("schedule_send", 16) +
    (c && c.pode_enviar_sem_confirmar && mail.contas.pode_enviar_sozinho ? "Enviar" : "Enviar para aprovação") + "</button></span></div></div>";
}

function painelDeEscrever() {
  return '<aside class="acervo-painel">' + alcaDoEmail() + '<div class="rolagem em-painel">' +
    '<div class="docs-ferramenta" id="nm-saida"></div>' +
    '<div class="docs-painel-cabeca">' + coroa(18) + '<span class="cresce">Pedir aqui</span><span>sobre este e-mail</span></div>' +
    '<div class="docs-conversa" id="nm-fala">' + falasDoEmail() + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Conferi</span></div><div class="em-conferencias" id="nm-conferi">' + conferenciasDoEmail() + "</div></div>" +
    '<div class="docs-chips"><button data-nm-chip="telefone">Adicionar o telefone</button><button data-nm-chip="contato">Copiar a outra conta</button>' +
    '<button class="adiante" data-nm-chip="formal">Deixar mais formal</button><button class="adiante" data-nm-chip="resumir">Resumir</button></div>' +
    '<div class="docs-pedido"><div class="docs-pedido-linha"><input type="text" id="nm-pedido" placeholder="Peça uma mudança no e-mail…">' +
    '<button class="enviar" id="nm-pedir" aria-label="Enviar">' + ic("arrow_forward", 18) + "</button></div>" +
    "<small>O e-mail só sai depois de aprovado em Aprovações.</small></div>" +
    "</div></aside>";
}

function falasDoEmail() {
  if (!mail.conversa.length) {
    return '<p class="docs-explica">Peça uma mudança no texto ou use os atalhos abaixo. O rascunho de resposta eu escrevo na caixa de entrada, a partir da mensagem recebida.</p>';
  }
  return mail.conversa.map((m) => m.autor === "pessoa"
    ? '<div class="docs-bolha">' + esc(m.texto) + "</div>"
    : '<div class="docs-resposta"><p>' + esc(m.texto) + "</p></div>").join("");
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
  if (mail.anexos.length) itens.push(linha("ok", plural(mail.anexos.length, "anexo") + " do Acervo · o destinatário recebe o arquivo inteiro"));
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
  return '<aside class="acervo-painel">' + alcaDoEmail() + '<div class="rolagem em-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + (r ? "Entrar de novo" : "Entrar em uma conta") + '</h3><span class="meta">' +
    (r ? esc(r.email) : "Detecto o servidor pelo domínio") + "</span></span>" +
    (r ? '<button class="voltar" id="mail-cancelar-reconectar" title="Conta nova" aria-label="Conta nova">' + ic("close", 18) + "</button>" : "") + "</div>" +
    '<div class="em-form">' +
    '<div class="ag-campo"><label>Endereço de e-mail</label><input type="text" id="mail-endereco" value="' + esc(r ? r.email : "") + '" placeholder="nome@dominio.com.br"' + (r ? " readonly" : "") + "></div>" +
    '<div class="ag-campo"><div class="em-rotulo-linha"><label>Senha ou senha de app</label><button class="em-ligacao acc" id="mail-como-gerar">como gerar</button></div>' +
    '<div class="em-senha"><input type="password" id="mail-senha" placeholder="••••••••"><button class="em-ligacao" id="mail-mostrar">mostrar</button></div></div>' +
    (r ? "" : '<div class="ag-campo"><label>Seu nome, como aparece para quem recebe</label><input type="text" id="mail-nome" placeholder="Matheus S. Uener"></div>') +
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
      '<div class="ag-campo"><label>Assinatura de rodapé</label><textarea id="mail-assinatura" placeholder="Matheus S. Uener · OAB/GO 00000"></textarea></div>') +
    '<div id="mail-prova"></div>' +
    '<div class="ag-form-rodape"><span class="ag-explica">A senha é guardada no cofre desta máquina e não sai dela.</span>' +
    '<button id="mail-testar">Testar</button><button class="primario com-icone" id="mail-entrar">' + ic("login", 16) + "Entrar</button></div>" +
    "</div></div></aside>";
}

/* -------------------------------------------------------- ligacoes */

function ligarEmail() {
  const raiz = $("email");
  const alca = raiz.querySelector("[data-em-alca]");
  if (alca) alca.onclick = () => { mail.largo = !mail.largo; raiz.classList.toggle("painel-largo", mail.largo); alca.innerHTML = ic(mail.largo ? "chevron_right" : "chevron_left", 18); };
  document.querySelectorAll("[data-em-visao]").forEach((b) => {
    b.onclick = () => (b.dataset.emVisao === "novo" ? telaEscrever() : mostrarEmail(b.dataset.emVisao));
  });
  const busca = $("mail-busca");
  busca.onkeydown = (e) => {
    if (e.key === "Enter") { mail.busca = busca.value.trim(); mail.pasta = mail.pasta === "esperando" ? "esperando" : "entrada"; mail.aberta = null; mostrarEmail("caixa"); }
    if (e.key === "Escape") { busca.value = ""; if (mail.busca) { mail.busca = ""; mostrarEmail("caixa"); } }
  };
  const escrever = $("em-escrever");
  if (escrever) escrever.onclick = () => telaEscrever();
  const voltar = $("em-voltar");
  if (voltar) voltar.onclick = () => { gravarRascunhoLocal(); mostrarEmail("caixa"); };

  if (mail.visao === "contas") return ligarContas();
  if (mail.visao === "novo") return ligarEscrever();
  ligarCaixa();
}

function ligarCaixa() {
  const raiz = $("email");
  raiz.querySelectorAll("[data-em-pasta]").forEach((b) => {
    b.onclick = async () => {
      if (b.classList.contains("adiante")) { mail.pasta = "arquivados"; }
      else mail.pasta = b.dataset.emPasta;
      mail.aberta = null; mail.envioAberto = null; mail.pedidoAberto = null;
      await carregarPasta();
      desenharEmail();
    };
  });
  raiz.querySelectorAll("[data-em-conta]").forEach((b) => {
    b.onclick = async () => {
      const c = mail.contas.contas.find((x) => x.id === b.dataset.emConta);
      if (!c) return;
      mail.conta = c; mail.aberta = null; mail.pasta = "entrada";
      await carregarPasta();
      desenharEmail();
    };
  });
  raiz.querySelectorAll("[data-em-filtro]").forEach((b) => {
    b.onclick = async () => { mail.filtro = b.dataset.emFiltro; mail.aberta = null; await carregarPasta(); desenharEmail(); };
  });
  raiz.querySelectorAll("[data-em-uid]").forEach((l) => { l.onclick = () => abrirMensagem(l.dataset.emUid); });
  raiz.querySelectorAll("[data-em-envio]").forEach((l) => { l.onclick = () => { mail.envioAberto = Number(l.dataset.emEnvio); desenharEmail(); }; });
  raiz.querySelectorAll("[data-em-pedido]").forEach((l) => { l.onclick = () => { mail.pedidoAberto = l.dataset.emPedido; desenharEmail(); }; });
  raiz.querySelectorAll("[data-em-rascunho]").forEach((l) => { l.onclick = () => telaEscrever(); });
  raiz.querySelectorAll("[data-em-aprovacoes]").forEach((b) => { b.onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); }; });
  raiz.querySelectorAll("[data-em-escrever-para]").forEach((b) => { b.onclick = () => telaEscrever({ para: b.dataset.emEscreverPara }); });

  const mais = $("mail-mais");
  if (mais) mais.onclick = async () => {
    mais.disabled = true;
    const r = await fetch("/api/email/caixa?filtro=" + mail.filtro + "&antes_de=" + encodeURIComponent(mail.caixa.ultimo_uid) + "&conta_id=" + mail.conta.id);
    if (!r.ok) { mais.disabled = false; return; }
    const d = await r.json();
    mail.caixa.mensagens = mail.caixa.mensagens.concat(d.mensagens);
    mail.caixa.mostrando += d.mostrando;
    mail.caixa.ultimo_uid = d.ultimo_uid || mail.caixa.ultimo_uid;
    mail.caixa.tem_mais = d.tem_mais;
    desenharEmail();
  };

  const m = mail.aberta;
  if (!m) return;
  const responder = () => telaEscrever({
    para: m.de_email,
    assunto: (m.assunto || "").toLowerCase().startsWith("re:") ? m.assunto : "Re: " + (m.assunto || ""),
    corpo: "",
  });
  ["mail-responder", "mail-responder-ic"].forEach((id) => { const b = $(id); if (b) b.onclick = responder; });
  const encaminhar = $("mail-encaminhar");
  if (encaminhar) encaminhar.onclick = () => telaEscrever({
    assunto: "Fwd: " + (m.assunto || ""),
    corpo: "\n\n---------- Mensagem encaminhada ----------\nDe: " + (m.de_nome || "") + " <" + m.de_email + ">\nAssunto: " + (m.assunto || "") + "\n\n" + (m.corpo || ""),
  });
  const arquivar = $("mail-arquivar");
  if (arquivar) arquivar.onclick = async () => {
    const r = await fetch("/api/email/arquivar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: m.uid, conta_id: mail.conta ? mail.conta.id : "" }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    const d = await r.json();
    if (d.aviso) avisoCert(d.aviso);
    mail.aberta = null;
    await carregarPasta();
    desenharEmail();
  };
  const maisMsg = $("mail-mais-msg");
  if (maisMsg) maisMsg.onclick = (e) => {
    e.stopPropagation();
    const itens = [{ icone: "content_copy", rotulo: "Copiar o endereço", acao: () => copiarTexto(m.de_email, "endereço copiado") }];
    if (m.prazo) itens.push({ icone: "add_task", rotulo: "Virar tarefa", acao: () => criarPrazoDoEmail(m, false) });
    menuNaLinha(maisMsg, itens);
  };
  raiz.querySelectorAll("[data-baixar]").forEach((b) => {
    b.onclick = () => window.open("/api/email/anexo?uid=" + encodeURIComponent(m.uid) + "&nome=" + encodeURIComponent(b.dataset.baixar) +
      (mail.conta ? "&conta_id=" + mail.conta.id : ""), "_blank");
  });
  raiz.querySelectorAll("[data-guardar]").forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      const r = await fetch("/api/email/anexo/guardar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid: m.uid, nome: b.dataset.guardar, conta_id: mail.conta ? mail.conta.id : "" }),
      });
      if (!r.ok) { b.disabled = false; avisoCert(await erroDe(r)); return; }
      const d = await r.json();
      estado.contratos = d.documentos;
      avisoCert("guardado no Acervo como " + d.guardado);
    };
  });
  raiz.querySelectorAll("[data-em-prazo]").forEach((b) => { b.onclick = () => criarPrazoDoEmail(m, b.dataset.emPrazo === "agenda"); });
  const preparar = $("mail-preparar");
  if (preparar) preparar.onclick = () => prepararRascunho(m, false);
  const comRascunho = $("mail-responder-rascunho");
  if (comRascunho) comRascunho.onclick = () => prepararRascunho(m, true);
  const abrirRascunho = $("mail-abrir-rascunho");
  if (abrirRascunho) abrirRascunho.onclick = () => abrirRascunhoNaComposicao();
  const aprovar = $("mail-aprovar-enviar");
  if (aprovar) aprovar.onclick = enviarRascunho;
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

async function prepararRascunho(m, abrirDepois) {
  if (mail.preparando) return;
  mail.preparando = true;
  desenharEmail();
  const r = await fetch("/api/email/rascunho", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid: m.uid, conta_id: mail.conta ? mail.conta.id : "" }),
  });
  mail.preparando = false;
  if (!r.ok) { avisoCert(await erroDe(r)); desenharEmail(); return; }
  mail.rascunho = Object.assign({ uid: m.uid }, await r.json());
  if (abrirDepois) return abrirRascunhoNaComposicao();
  desenharEmail();
}

function abrirRascunhoNaComposicao() {
  const r = mail.rascunho;
  if (!r) return;
  telaEscrever({ para: r.para.join(", "), assunto: r.assunto, corpo: r.rascunho });
}

/* "Aprovar e enviar": o pedido nasce aqui e vai para a fila. */
async function enviarRascunho() {
  const r = mail.rascunho;
  if (!r) return;
  const pedido = { conta_id: mail.conta ? mail.conta.id : "", para: r.para.join(", "), cc: "", cco: "", assunto: r.assunto, corpo: r.rascunho, anexos: [] };
  const d = await mandarPedido(pedido);
  if (!d) return;
  mail.rascunho = null;
  if (d.aguardando_aprovacao) avisoCert("o envio parou na fila de Aprovações — nada sai sem o seu sim");
  else avisoCert("enviado para " + (d.para || []).join(", "));
  await carregarFilaDeEmail();
  desenharEmail();
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
  ["nm-assunto", "nm-corpo", "nm-cc", "nm-cco"].forEach((id) => { const el = $(id); if (el) el.oninput = mudou; });

  $("nm-anexar").onclick = escolherAnexos;
  $("nm-anexar-2").onclick = escolherAnexos;
  $("nm-previa").onclick = verPrevia;
  $("nm-salvar").onclick = () => { gravarRascunhoLocal(); avisoCert("rascunho guardado nesta máquina"); };
  $("nm-descartar").onclick = async () => {
    if (($("nm-corpo").value.trim() || mail.para.length) && !(await confirmar({ titulo: "Descartar este e-mail?", contexto: "E-mail › Novo e-mail", texto: "O rascunho some desta máquina.", confirmar: "Descartar", perigo: true }))) return;
    apagarRascunhoLocal();
    mail.anexos = [];
    mostrarEmail("caixa");
  };
  $("nm-enviar").onclick = enviarEmail;

  raiz.querySelectorAll("[data-nm-chip]").forEach((b) => { b.onclick = () => atalhoDoEmail(b.dataset.nmChip); });
  const pedir = () => { const campo = $("nm-pedido"); const t = campo.value.trim(); if (!t) return; campo.value = ""; pedirNoEmail(t); };
  $("nm-pedir").onclick = pedir;
  $("nm-pedido").onkeydown = (e) => { if (e.key === "Enter") pedir(); };

  desenharAnexos();
  atualizarConferencias();
  const foco = mail.para.length ? (mail.assunto ? $("nm-corpo") : $("nm-assunto")) : campoPara;
  if (foco) foco.focus();
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

/* Sem motor para reescrever o e-mail: os atalhos que dao para cumprir agora
   sao os que mexem com o que a maquina ja sabe. */
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
    return;
  }
  avisoCert("reescrever o e-mail ainda não tem motor nesta máquina — por enquanto eu preparo o rascunho de resposta na caixa de entrada");
}

function pedirNoEmail(texto) {
  mail.conversa.push({ autor: "pessoa", texto: texto });
  mail.conversa.push({ autor: "paulus", texto: "Pedidos sobre o texto do e-mail ainda não têm motor nesta máquina. O que faço agora: preparar o rascunho de resposta a uma mensagem recebida (na caixa de entrada) e conferir este e-mail antes de sair — veja “Conferi”, logo abaixo." });
  const caixa = $("nm-fala");
  if (caixa) { caixa.innerHTML = falasDoEmail(); caixa.scrollTop = caixa.scrollHeight; }
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

async function escolherAnexos() {
  const alvo = $("nm-saida");
  if (!alvo) return;
  alvo.innerHTML = '<div class="painel"><p class="nota">lendo o Acervo…</p></div>';
  let d;
  try { d = await (await fetch("/api/email/anexaveis")).json(); } catch (err) { alvo.innerHTML = ""; return; }
  alvo.innerHTML = '<div class="painel"><h3>Anexar do Acervo</h3>' +
    (d.arquivos.length
      ? '<div class="ag-escolher">' + d.arquivos.slice(0, 60).map((a) =>
          '<div class="ag-ligado">' + glifo(a.nome) + "<span>" + esc(a.nome) + '</span><small class="contagem">' + String(a.mb).replace(".", ",") + ' MB</small><button data-anexo="' + esc(a.path) + '" data-nome="' + esc(a.nome) + '" data-mb="' + a.mb + '">Anexar</button></div>').join("") + "</div>"
      : '<p class="explica">O Acervo está vazio.</p>') +
    '<div class="linha-form"><button data-doc-fechar-ferramenta="1">Fechar</button></div></div>';
  alvo.querySelector("[data-doc-fechar-ferramenta]").onclick = () => { alvo.innerHTML = ""; };
  alvo.querySelectorAll("[data-anexo]").forEach((b) => {
    b.onclick = () => {
      if (!mail.anexos.some((a) => a.path === b.dataset.anexo)) mail.anexos.push({ path: b.dataset.anexo, nome: b.dataset.nome, mb: Number(b.dataset.mb) || 0 });
      desenharAnexos();
      gravarRascunhoLocal();
      atualizarConferencias();
    };
  });
}

function desenharAnexos() {
  const alvo = $("nm-anexos");
  if (!alvo) return;
  const mb = mail.anexos.reduce((s, a) => s + (Number(a.mb) || 0), 0);
  const n = $("nm-anexos-n");
  if (n) n.textContent = mail.anexos.length ? plural(mail.anexos.length, "anexo") + (mb ? " · " + mb.toFixed(1).replace(".", ",") + " MB" : "") : "Sem anexos";
  alvo.innerHTML = mail.anexos.map((a, i) =>
    '<div class="em-anexo">' + glifo(a.nome) + '<span class="duas-linhas"><b>' + esc(a.nome) + "</b><small>" +
    (a.mb ? String(a.mb).replace(".", ",") + " MB · " : "") + "do Acervo · o destinatário recebe o arquivo inteiro</small></span>" +
    '<span class="em-msg-acoes"><button data-tira="' + i + '" title="Remover">' + ic("close", 18) + "</button></span></div>").join("");
  alvo.querySelectorAll("[data-tira]").forEach((b) => {
    b.onclick = () => { mail.anexos.splice(Number(b.dataset.tira), 1); desenharAnexos(); gravarRascunhoLocal(); atualizarConferencias(); };
  });
}

async function verPrevia() {
  const alvo = $("nm-saida");
  alvo.innerHTML = '<div class="painel"><p class="nota">montando…</p></div>';
  const r = await fetch("/api/email/previa", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pedidoDoEnvio()),
  });
  if (!r.ok) { alvo.innerHTML = '<div class="painel"><p class="explica">' + esc(await erroDe(r)) + "</p></div>"; return; }
  const d = await r.json();
  alvo.innerHTML = '<div class="painel"><h3>Como vai chegar</h3>' +
    '<p class="explica">De ' + esc(d.de) + " · para " + esc(d.para.join(", ")) + (d.cco.length ? " · cco " + esc(d.cco.join(", ")) : "") + "</p>" +
    "<b>" + esc(d.assunto) + "</b>" +
    '<div class="email-corpo">' + esc(d.corpo) + "</div>" +
    (d.anexos.length ? d.anexos.map((a) => '<div class="ag-ligado-linha"><span>' + esc(a.nome) + "</span><small>" + String(a.kb).replace(".", ",") + " KB</small></div>").join("") : "") +
    '<p class="explica">' + esc(d.resumo || "") + "</p>" +
    '<div class="linha-form"><button data-doc-fechar-ferramenta="1">Fechar</button></div></div>';
  alvo.querySelector("[data-doc-fechar-ferramenta]").onclick = () => { alvo.innerHTML = ""; };
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
  depoisDoEnvio(d);
}

function depoisDoEnvio(d) {
  const caixa = document.querySelector(".em-compor");
  if (!caixa) return;
  if (d.aguardando_aprovacao) {
    caixa.innerHTML = '<div class="em-vazio grande"><h4>Esperando o seu sim</h4><p>' + esc(d.pedido.titulo) + " — " + esc(d.pedido.resumo) +
      '</p><p>E-mail que sai não volta, então o pedido parou na fila de aprovações. Nada foi enviado ainda.</p>' +
      '<div class="em-vazio-acao"><button class="primario com-icone" id="nm-fila">' + ic("verified", 16) + "Abrir a fila</button>" +
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

