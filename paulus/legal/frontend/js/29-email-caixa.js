/* ------------------------------------------------------ e-mail: caixa */
/*
   A caixa de entrada na linguagem da Contas 4a: cartao limpo no centro,
   uma coisa por vez, serifa nos titulos, fios finos. Tres opcoes em revisao:

   "a" - Fila: uma mensagem por vez, na ordem do que pede resposta (prazo
         primeiro). Responder, arquivar ou deixar para depois; as proximas
         aparecem embaixo. "Ver a caixa inteira" leva a lista de "b".
   "b" - Passos: um cartao so. A lista; ao clicar, o cartao vira a
         mensagem, com a volta no alto, como os passos da Contas.
   "c" - Duas folhas: a lista e a mensagem lado a lado, dois cartoes.

   Troca so o desenho da visao "caixa"; os ganchos (ids mail-*, data-em-*)
   sao os de js/18-email.js, que continua fazendo o trabalho.
   Vale "a" (aprovada). ?caixa=b|c abre as outras para comparar;
   ?caixa_modo=lista abre "a" na lista. Precisa de js/28-email-contas.js
   (ecRegras, ecEstado, ecNovo, ecContaLigada) e de css/26-email-contas.css
   (o cartao ec-).

   Conta que precisa entrar de novo (senha recusada, sem senha guardada ou
   login do Google/Microsoft vencido) vai para o fluxo da Contas, nunca para
   uma caixa quebrada.
*/

function desenhoDaCaixa() {
  const v = new URLSearchParams(location.search).get("caixa");
  return v === "b" || v === "c" ? v : "a";
}

const EX_EXTENSO = ["Nenhuma", "Uma", "Duas", "Três", "Quatro", "Cinco", "Seis", "Sete", "Oito", "Nove", "Dez"];

let exChave = "";

function exPede(m) { return !m.respondido && (!m.lido || !!m.prazo); }

function exFila() {
  const k = mail.caixa;
  if (!k) return [];
  const conta = mail.conta ? mail.conta.id : "";
  if (!mail.exFila || mail.exFilaConta !== conta) {
    const p = (m) => m.prazo || "9999";
    mail.exFila = k.mensagens.filter(exPede).sort((a, b) => (p(a) < p(b) ? -1 : p(a) > p(b) ? 1 : 0)).map((m) => m.uid);
    mail.exFilaConta = conta;
    mail.exIndice = 0;
  }
  return mail.exFila.map((uid) => k.mensagens.find((m) => m.uid === uid)).filter(Boolean);
}

function exModo() {
  if (!mail.exModo) mail.exModo = new URLSearchParams(location.search).get("caixa_modo") === "lista" ? "lista" : "fila";
  return mail.exModo;
}

function exIni(nome) { return '<span class="ex-ini">' + esc(iniciaisDoRemetente(nome)) + "</span>"; }

function exNaCaixa() { return mail.pasta === "entrada" || mail.pasta === "esperando"; }

function exPrazoCurto(prazo) { return rotuloDoPrazo(prazo).replace(/^prazo /, ""); }

/* O envio sai sozinho so quando a conta e o programa deixam; senao, fila. */
function exSaiSozinho() {
  const c = mail.conta;
  return !!(c && c.pode_enviar_sem_confirmar && mail.contas && mail.contas.pode_enviar_sozinho);
}

/* ------------------------------------------------ conta que precisa entrar */

function exPrecisaEntrar(c) {
  if (!c) return false;
  if (c.por_login) return !!(c.precisa_entrar || !c.tem_senha);
  return !!(c.ultimo_erro || !c.tem_senha);
}

/* Leva ao "entrar de novo" da Contas 4a: o login do provedor para a conta
   de login, o passo da senha para a de senha. Dando certo, a Contas abre a
   caixa desta conta. */
async function exEntrarDeNovo(c) {
  if (!c) return mostrarEmail("contas");
  if (c.por_login) {
    await mostrarEmail("contas");
    if (typeof entrarDeNovoOAuth === "function") entrarDeNovoOAuth(c, ecContaLigada);
    return;
  }
  Object.assign(ecEstado(), ecNovo(), { passo: "senha", reconectar: c, email: c.email, abrirDepois: true });
  await mostrarEmail("contas");
  ecFoco();
}

/* O pedido de envio de sempre (mandarPedido). A conta de login nao tem
   senha para perguntar: se o servidor pede para entrar de novo, vai para
   a Contas. */
async function exMandar(pedido) {
  const c = mail.conta;
  if (!c || !c.por_login) return mandarPedido(pedido);
  let r;
  try {
    r = await fetch("/api/email/enviar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pedido) });
  } catch (err) { avisoCert(String(err)); return null; }
  if (r.status === 401) { avisoCert(await erroDe(r)); exEntrarDeNovo(c); return null; }
  if (!r.ok) { avisoCert(await erroDe(r)); return null; }
  return r.json();
}

/* ------------------------------------------------------------ lista */

function exTopo() {
  const c = mail.conta;
  return '<div class="ex-topo"><span class="ec-marca"><img src="img/paulus-logo.png" alt=""><span>PAULUS · E-mail</span></span>' +
    (c ? '<button class="ex-conta" data-ex-conta="1" title="Trocar de conta">' + avatarDaConta(c) + "<span>" + esc(c.email) + "</span>" + ic("expand_more", 16) + "</button>" : "") + "</div>";
}

function exTituloDaPasta() {
  const k = mail.caixa;
  if (exNaCaixa()) {
    if (mail.erroCaixa) return ["Não consegui abrir a caixa", "O servidor respondeu: " + mail.erroCaixa];
    const lista = k ? k.mensagens : [];
    const pedem = lista.filter(exPede).length;
    const urg = lista.filter((m) => m.prazo && !m.respondido).sort((a, b) => (a.prazo < b.prazo ? -1 : 1))[0];
    return [mail.pasta === "esperando" ? "Esperando resposta" : "Caixa de entrada",
      (pedem ? (EX_EXTENSO[pedem] || pedem) + (pedem === 1 ? " mensagem pede resposta." : " mensagens pedem resposta.") : "Nada pede resposta agora.") +
      (urg ? " O prazo mais perto: " + exPrazoCurto(urg.prazo) + ", " + (urg.de_nome || urg.de_email) + "." : "")];
  }
  if (mail.pasta === "enviados") return ["Enviados", "O que saiu pelo PAULUS fica anotado aqui; a cópia completa está no seu servidor."];
  if (mail.pasta === "rascunhos") return ["Rascunhos", "Guardados nesta máquina até sair."];
  if (mail.pasta === "aprovacao") return ["Aguardando o seu sim", "Os envios que pedem o seu sim esperam aqui. E-mail enviado não volta."];
  return ["Arquivados", "Ler a pasta de arquivo do servidor daqui ainda vem adiante."];
}

function exPastas() {
  return '<nav class="ex-pastas">' + PASTAS_DE_EMAIL.map((p) => {
    const n = contagemDaPasta(p.id);
    const acc = n && (p.id === "esperando" || p.id === "aprovacao") ? " acc" : "";
    return '<button class="ex-pasta' + (p.id === mail.pasta ? " ativa" : "") + (p.adiante ? " adiante" : "") + '" data-em-pasta="' + p.id + '">' +
      "<span>" + p.rotulo + '</span><span class="em-conta' + acc + '">' + (n || "") + "</span></button>";
  }).join("") + "</nav>";
}

function exLinhaG(attr, aberta, nova, ini, nome, assunto, quando, lado) {
  return '<button class="ex-linha' + (nova ? " nova" : "") + (aberta ? " aberta" : "") + '" ' + attr + ">" + ini +
    '<span class="ex-linha-texto"><b>' + esc(nome) + "</b><span>" + esc(assunto || "(sem assunto)") + "</span></span>" +
    '<span class="ex-linha-lado"><small>' + esc(quando || "") + "</small>" + (lado || "") + "</span></button>";
}

function exLinha(m) {
  const lado = m.prazo && !m.respondido ? "<em>" + esc(exPrazoCurto(m.prazo)) + "</em>" : m.tem_anexo ? ic("attach_file", 15) : "";
  if (exAbreNaLista()) {
    const aberta = mail.exLinhaAberta === m.uid;
    return '<div class="ex-item' + (aberta ? " aberta" : "") + '">' +
      exLinhaG('data-ex-abre="' + esc(m.uid) + '" aria-expanded="' + aberta + '"', aberta, !m.lido, exIni(m.de_nome || m.de_email), m.de_nome || m.de_email, m.assunto, m.quando_curto, lado) +
      (aberta ? exDentro(m) : "") + "</div>";
  }
  return exLinhaG('data-em-uid="' + esc(m.uid) + '"', mail.aberta && mail.aberta.uid === m.uid, !m.lido, exIni(m.de_nome || m.de_email),
    m.de_nome || m.de_email, m.assunto, m.quando_curto, lado);
}

function exVazio(titulo, texto, acao) {
  return '<div class="ex-vazio"><h4>' + titulo + "</h4><p>" + texto + "</p>" + (acao || "") + "</div>";
}

/* Os botoes de quando a caixa nao abre: entrar de novo pela Contas, abrir
   a Contas ou tentar outra vez. */
function exBotoesDoErro() {
  return '<div class="ec-botoes"><button data-ex-tentar="1">Tentar de novo</button><button data-em-visao="contas">Abrir contas</button>' +
    (mail.conta ? '<button class="primario" data-ex-entrar="1">Entrar de novo</button>' : "") + "</div>";
}

function exListaCorpo() {
  if (exNaCaixa()) {
    if (mail.erroCaixa) return exVazio("Não consegui abrir", esc(mail.erroCaixa), exBotoesDoErro());
    const k = mail.caixa;
    if (!k) return exVazio("Abrindo", "Buscando as mensagens no servidor.");
    const itens = mail.pasta === "esperando" ? k.mensagens.filter((m) => !m.respondido && !m.lido) : k.mensagens;
    if (!itens.length) return exVazio("Nada aqui", "Nenhuma mensagem nesta pasta.");
    const pedem = itens.filter(exPede), resto = itens.filter((m) => !exPede(m));
    return (pedem.length ? '<div class="ex-grupo acc">Pedem resposta · ' + pedem.length + "</div>" + pedem.map(exLinha).join("") : "") +
      (resto.length ? '<div class="ex-grupo">' + (pedem.length ? "O resto" : "Mensagens") + " · " + resto.length + "</div>" + resto.map(exLinha).join("") : "") +
      '<div class="ex-rodape"><span>' + (mail.pasta === "esperando" ? itens.length + " esperando" : k.mostrando + " de " + k.total) + '</span><span class="cresce"></span>' +
      (k.tem_mais ? '<button class="sv-ligacao" id="mail-mais">Carregar mais</button>' : "") + "</div>";
  }
  if (mail.pasta === "enviados") {
    return mail.envios.length
      ? mail.envios.map((e, i) => exLinhaG('data-em-envio="' + i + '"', mail.envioAberto === i, false, exIni((e.para || [])[0] || "?"),
          (e.para || []).join(", ") || "—", e.assunto, quandoCurto(e.quando), (e.anexos || []).length ? ic("attach_file", 15) : "")).join("")
      : exVazio("Nada enviado daqui", "O que sair pelo PAULUS fica anotado aqui.");
  }
  if (mail.pasta === "rascunhos") {
    const r = lerRascunhoLocal();
    return r ? exLinhaG('data-em-rascunho="1"', false, false, '<span class="ex-ini">' + ic("draft", 16) + "</span>", r.para || "sem destinatário", r.assunto, quandoCurto(r.quando), "")
      : exVazio("Nenhum rascunho", "O que você começa a escrever fica guardado aqui até sair.");
  }
  if (mail.pasta === "aprovacao") {
    return mail.fila.length
      ? mail.fila.map((p) => exLinhaG('data-em-pedido="' + esc(p.id) + '"', mail.pedidoAberto === p.id, true, '<span class="ex-ini">' + ic("schedule_send", 16) + "</span>",
          p.titulo, p.resumo, quandoCurto(p.criado_em), "<em>esperando você</em>")).join("")
      : exVazio("Nada esperando", "Nenhum envio esperando o seu sim agora.");
  }
  return exVazio("Ainda não listo o arquivo", "Arquivar move a mensagem para a pasta de arquivo do seu servidor.");
}

function exCartaoLista(extra) {
  const [titulo, lide] = exTituloDaPasta();
  return '<section class="ec-cartao ex-cartao">' + exTopo() + (extra || "") + "<h2>" + esc(titulo) + '</h2><p class="ec-lide">' + esc(lide) + "</p>" +
    exPastas() + '<div class="ex-lista">' + exListaCorpo() + "</div></section>";
}

/* A caixa nao abriu: na fila, no lugar de "nada pede resposta". */
function exCartaoErro() {
  return '<section class="ec-cartao ex-cartao">' + exTopo() + "<h2>Não consegui abrir a caixa</h2>" +
    '<p class="ec-lide">O servidor respondeu: ' + esc(mail.erroCaixa) + "</p>" + exBotoesDoErro() + "</section>";
}

/* -------------------------------------------------------- mensagem */

function exEntendi(m) {
  return esc(m.de_nome || m.de_email) + (m.de_cadastro && m.de_cadastro !== m.de_nome ? ", da " + esc(m.de_cadastro) + "," : "") +
    " escreveu sobre “" + esc(m.assunto || "sem assunto") + "”." + (m.prazo ? " O texto menciona um prazo." : "") +
    (m.anexos && m.anexos.length ? " Vem com " + plural(m.anexos.length, "anexo") + "." : "") + (m.respondido ? " Você já respondeu." : "");
}

function exNotas(m) {
  let rascunho;
  const meu = mail.rascunho && mail.rascunho.uid === m.uid;
  if (!m.pode_rascunhar) rascunho = "<p>Esta conta não permite que eu escreva rascunhos.</p>";
  else if (mail.preparando) rascunho = '<p class="ex-abrindo">Escrevendo… leva cerca de um minuto nesta máquina.</p>';
  else if (meu) {
    rascunho = '<div class="ex-rascunho"><b>' + esc(mail.rascunho.assunto) + "</b><p>" + esc(mail.rascunho.rascunho) + "</p></div>" +
      '<span class="ex-nota-acoes"><button class="sv-ligacao" id="mail-abrir-rascunho">Abrir o rascunho</button>' +
      '<button class="primario com-icone" id="mail-aprovar-enviar">' + ic("check", 16) + (exSaiSozinho() ? "Enviar" : "Enviar para aprovação") + "</button></span>";
  } else {
    rascunho = '<span class="ex-nota-acoes"><span class="ex-cinza">Leva cerca de um minuto, por isso só faço quando você pede.</span>' +
      '<button class="com-icone" id="mail-preparar">' + ic("auto_awesome", 16) + "Preparar resposta</button></span>";
  }
  return '<div class="ex-notas"><section class="ex-nota"><span class="sv-kicker">' + coroa(14) + "O que eu entendi</span><p>" + exEntendi(m) + "</p></section>" +
    (m.prazo
      ? '<section class="ex-nota prazo"><span class="sv-kicker">Prazo detectado</span><div class="ex-prazo"><b>' + esc(dataCurta(m.prazo)) + "</b>" +
        (m.prazo_trecho ? "<span>“" + esc(m.prazo_trecho) + "”</span>" : "") + "</div>" +
        '<span class="ex-nota-acoes"><button class="sv-ligacao" data-em-prazo="agenda">' + ic("event_upcoming", 15) + "Criar na Agenda</button>" +
        '<button class="sv-ligacao" data-em-prazo="tarefa">' + ic("add_task", 15) + "Criar tarefa</button></span></section>"
      : "") +
    '<section class="ex-nota"><span class="sv-kicker">Rascunho de resposta' + (meu ? ' · <em class="ex-acc">esperando você</em>' : "") + "</span>" + rascunho + "</section></div>";
}

function exIcones(comResponder) {
  return '<span class="em-msg-acoes">' + (comResponder ? '<button id="mail-responder-ic" title="Responder">' + ic("reply", 18) + "</button>" : "") +
    '<button id="mail-encaminhar" title="Encaminhar">' + ic("forward", 18) + "</button>" +
    '<button id="mail-arquivar" title="Arquivar">' + ic("archive", 18) + "</button>" +
    '<button id="mail-mais-msg" title="Mais">' + ic("more_horiz", 18) + "</button></span>";
}

function exVolta() {
  const p = PASTAS_DE_EMAIL.find((x) => x.id === mail.pasta) || PASTAS_DE_EMAIL[0];
  return '<button class="ec-quem" data-ex-voltar="1">' + ic("arrow_back", 16) + "<span>" + esc(p.rotulo) + "</span></button>";
}

function exCabecaMsg(m, kicker) {
  const c = mail.conta;
  return '<div class="ex-msg-topo"><span class="sv-kicker">' + kicker + "</span>" + exIcones(false) + "</div>" +
    "<h2>" + esc(m.assunto || "(sem assunto)") + "</h2>" +
    '<p class="ex-meta">' + esc(m.de_nome || "") + (m.de_nome ? " · " : "") + esc(m.de_email) + (m.quando_curto ? " · " + esc(m.quando_curto) : "") + (c ? " · para " + esc(c.email) : "") + "</p>";
}

function exCorpoMsg(m) {
  return '<p class="ex-corpo">' + corpoComPrazo(m.corpo, m.prazo_trecho) + "</p>" + (m.anexos && m.anexos.length ? blocoDeAnexos(m.anexos, true) : "");
}

function exKicker(m) {
  return "De " + esc(m.de_nome || m.de_email) + (m.de_cadastro && m.de_cadastro !== m.de_nome ? " · " + esc(m.de_cadastro) : "");
}

function exCartaoMsg(m, volta) {
  return '<section class="ec-cartao ex-cartao">' + (volta ? exVolta() : "") + exCabecaMsg(m, exKicker(m)) + exCorpoMsg(m) +
    (exRespAtiva(m) ? exResposta(m, false) : exNotas(m) +
    '<div class="ec-botoes ex-botoes">' + (m.pode_rascunhar ? '<button class="com-icone" id="mail-responder-rascunho">' + ic("auto_awesome", 16) + "Responder com o rascunho</button>" : "") +
    '<button class="primario com-icone" id="mail-responder">' + ic("reply", 16) + "Responder</button></div>") + "</section>";
}

function exCartaoSimples(volta) {
  if (mail.pasta === "enviados" && mail.envioAberto !== null && mail.envios[mail.envioAberto]) {
    const e = mail.envios[mail.envioAberto];
    return '<section class="ec-cartao ex-cartao">' + (volta ? exVolta() : "") + '<span class="sv-kicker">Enviado</span><h2>' + esc(e.assunto || "(sem assunto)") + "</h2>" +
      '<p class="ex-meta">de ' + esc(e.de) + " · para " + esc((e.para || []).join(", ")) + " · " + esc(quandoCurto(e.quando)) + "</p>" +
      '<p class="ec-lide">O texto completo está na pasta de enviados do seu servidor; aqui fica o registro de que saiu.</p>' +
      ((e.anexos || []).length ? blocoDeAnexos(e.anexos.map((n) => ({ nome: n })), false) : "") +
      '<div class="ec-botoes"><button class="primario com-icone" data-em-escrever-para="' + esc((e.para || []).join(", ")) + '">' + ic("edit", 16) + "Escrever de novo</button></div></section>";
  }
  if (mail.pasta === "aprovacao" && mail.pedidoAberto !== null) {
    const p = mail.fila.find((x) => x.id === mail.pedidoAberto);
    if (p) {
      return '<section class="ec-cartao ex-cartao">' + (volta ? exVolta() : "") + '<span class="sv-kicker ex-acc">Esperando o seu sim</span><h2>' + esc(p.titulo) + "</h2>" +
        '<p class="ex-meta">pedido em ' + esc(quandoCurto(p.criado_em)) + "</p>" + '<p class="ec-lide">' + esc(p.resumo || "") + "</p>" +
        '<div class="ec-botoes"><span class="ex-cinza cresce">O e-mail só sai depois do seu sim.</span><button class="primario com-icone" data-em-aprovacoes="1">' + ic("verified", 16) + "Decidir em Aprovações</button></div></section>";
    }
  }
  return "";
}

function exAlgoAberto() {
  if (exNaCaixa()) return !!mail.aberta;
  return (mail.pasta === "enviados" && mail.envioAberto !== null) || (mail.pasta === "aprovacao" && mail.pedidoAberto !== null);
}

function exCartaoAberto(volta) {
  return exNaCaixa() ? exCartaoMsg(mail.aberta, volta) : exCartaoSimples(volta);
}

/* ------------------------------------------------------------ fila */

function exCartaoFila() {
  if (mail.erroCaixa) return exCartaoErro();
  const fila = exFila();
  const i = mail.exIndice || 0;
  const verTudo = '<button class="sv-ligacao" data-ex-modo="lista">' + ic("inbox", 15) + "Ver a caixa inteira</button>";
  if (!fila.length || i >= fila.length) {
    return '<section class="ec-cartao ex-cartao">' + exTopo() + "<h2>" + (fila.length ? "Você passou por todas" : "Nada pede resposta") + "</h2>" +
      '<p class="ec-lide">' + (fila.length ? "As que ficaram para depois continuam na caixa, na mesma ordem." : "Nenhuma mensagem nova nem prazo esperando por você.") + "</p>" +
      '<div class="ec-botoes">' + (fila.length ? '<button data-ex-recomecar="1">Começar de novo</button>' : "") + '<button class="primario" data-ex-modo="lista">Ver a caixa inteira</button></div></section>';
  }
  const item = fila[i];
  const m = mail.aberta && mail.aberta.uid === item.uid ? mail.aberta : null;
  const falhou = !m && mail.exFalhou === item.uid;
  const kicker = (item.prazo && !item.respondido ? '<span class="ex-acc">Prazo ' + esc(exPrazoCurto(item.prazo)) + "</span> · " : "Pede resposta · ") + exKicker(item);
  const cartao = '<section class="ec-cartao ex-cartao">' +
    '<div class="ex-topo"><span class="ec-marca"><img src="img/paulus-logo.png" alt=""><span>PAULUS · E-mail</span></span>' +
    '<span class="ex-contagem"><b>' + (i + 1) + "</b> de " + fila.length + " pedem resposta</span></div>" +
    (m ? exCabecaMsg(m, kicker) + exCorpoMsg(m) + (exRespAtiva(m) ? exResposta(m, true) : exNotas(m))
       : '<div class="ex-msg-topo"><span class="sv-kicker">' + kicker + "</span></div><h2>" + esc(item.assunto || "(sem assunto)") + "</h2>" +
         '<p class="ex-corpo ex-abrindo">' + (falhou ? "Não consegui abrir esta mensagem." : "abrindo…") + "</p>") +
    (exRespAtiva(m) ? "" : '<div class="ec-botoes ex-botoes">' + (m ? '<button class="com-icone" id="mail-arquivar-fila" data-ex-arquivar="1">' + ic("archive", 16) + "Arquivar</button>" : "") +
    (falhou ? '<button data-ex-tentar-msg="1">Tentar de novo</button>' : "") +
    '<button class="com-icone" data-ex-depois="1">Depois' + ic("arrow_forward", 16) + '</button><span class="cresce"></span>' +
    (m ? (m.pode_rascunhar ? '<button class="com-icone" id="mail-responder-rascunho">' + ic("auto_awesome", 16) + "Com o rascunho</button>" : "") +
      '<button class="primario com-icone" id="mail-responder">' + ic("reply", 16) + "Responder</button>" : "") + "</div>") + "</section>";
  const proximas = fila.slice(i + 1, i + 4);
  return cartao + '<div class="ex-proximas">' + (proximas.length ? '<span class="sv-kicker">Depois desta</span>' + proximas.map((p, j) =>
    '<button class="ex-proxima" data-ex-ir="' + (i + 1 + j) + '"><b>' + esc(p.de_nome || p.de_email) + "</b><span>" + esc(p.assunto || "") + "</span>" +
    (p.prazo ? "<em>" + esc(exPrazoCurto(p.prazo)) + "</em>" : "") + "</button>").join("") : "") +
    '<div class="ex-fim-links">' + verTudo + "</div></div>";
}

/* ------------------------------------------------------- responder */
/*
   A resposta abre ali mesmo, embaixo da mensagem (na fila, no cartao ou na
   linha aberta), no lugar das notas. Sai pelo mesmo pedido de envio do
   Escrever (fila de Aprovacoes, quando a conta pede). "Tela cheia" leva o
   texto para o Escrever de sempre.
*/

function exRespAtiva(m) { return !!(m && mail.exResp && mail.exResp.uid === m.uid); }

function exConferir(r, m) {
  const itens = [];
  const linha = (ok, t) => '<div class="em-conferencia ' + (ok ? "ok" : "aviso") + '">' + ic(ok ? "check_circle" : "error", 16) + "<span>" + t + "</span></div>";
  itens.push(m.de_cadastro ? linha(true, "Destinatário no cadastro · " + esc(m.de_cadastro)) : linha(false, esc(r.para) + " não está no cadastro"));
  if (/\banex[oa]/i.test(r.corpo)) itens.push(linha(false, "O texto cita anexo, mas nenhum arquivo vai junto"));
  const valores = r.corpo.match(/R\$\s?[\d.]+(,\d{2})?/g);
  if (valores) itens.push(linha(true, "Cita " + esc(valores.slice(0, 2).join(", ")) + " · confira antes"));
  itens.push(linha(true, "Sai por " + esc(mail.conta ? mail.conta.email : "") + (exSaiSozinho() ? "" : " · passa por Aprovações")));
  return itens.join("");
}

function exResposta(m, naFila) {
  const r = mail.exResp;
  const c = mail.conta;
  if (r.estado === "enviado") {
    const esperando = r.retorno && r.retorno.aguardando_aprovacao;
    return '<div class="ex-resp feito"><span class="sv-kicker">' + ic(esperando ? "schedule_send" : "check_circle", 15) + "Resposta</span>" +
      "<h3>" + (esperando ? "Esperando o seu sim" : "Enviada") + "</h3>" +
      "<p>" + (esperando ? "Parou na fila de Aprovações para " + esc(r.para) + ". Nada saiu ainda; e-mail enviado não volta." : "Saiu pelo servidor da sua conta para " + esc(r.para) + ".") + "</p>" +
      '<div class="ex-resp-acoes">' + (esperando ? '<button class="com-icone" data-em-aprovacoes="1">' + ic("verified", 16) + "Abrir Aprovações</button>" : "") +
      '<span class="cresce"></span>' + (naFila ? '<button class="primario com-icone" data-ex-depois="1">Próxima' + ic("arrow_forward", 16) + "</button>"
        : '<button data-ex-resp-fechar="1">Fechar</button>') + "</div></div>";
  }
  const preparando = r.estado === "preparando";
  return '<div class="ex-resp' + (mail.exRespEntra === m.uid ? " entra" : "") + '">' +
    '<div class="ex-resp-topo"><span class="sv-kicker">' + ic("reply", 15) + "Resposta</span>" +
    '<span class="ex-resp-para">para <b>' + esc(r.para) + "</b></span></div>" +
    '<input type="text" class="ex-resp-assunto" id="ex-resp-assunto" value="' + esc(r.assunto) + '" aria-label="Assunto">' +
    (preparando
      ? '<p class="ex-resp-preparando">' + coroa(16) + "Escrevendo o rascunho a partir da mensagem… leva cerca de um minuto nesta máquina.</p>"
      : '<textarea class="ex-resp-texto" id="ex-resp-texto" placeholder="Escreva a resposta…" rows="6">' + esc(r.corpo) + "</textarea>") +
    (c && c.assinatura ? '<div class="ex-resp-assinatura">' + esc(c.assinatura) + "</div>" : "") +
    (preparando ? "" : '<div class="ex-resp-conferi" id="ex-resp-conferi">' + exConferir(r, m) + "</div>") +
    '<div class="ex-resp-acoes"><button class="sv-ligacao" data-ex-resp-descartar="1">' + ic("delete", 15) + "Descartar</button>" +
    '<button class="sv-ligacao" data-ex-resp-cheia="1">' + ic("fullscreen", 15) + "Tela cheia · anexos</button>" +
    (m.pode_rascunhar && !preparando && !r.corpo.trim() ? '<button class="sv-ligacao" data-ex-resp-rascunho="1">' + ic("auto_awesome", 15) + "Escrever o rascunho para mim</button>" : "") +
    '<span class="cresce"></span><button class="primario com-icone" data-ex-resp-enviar="1"' + (preparando || r.estado === "enviando" ? " disabled" : "") + ">" +
    ic("schedule_send", 16) + (r.estado === "enviando" ? "Enviando…" : exSaiSozinho() ? "Enviar" : "Enviar para aprovação") + "</button></div></div>";
}

async function exResponder(comRascunho) {
  const m = mail.aberta;
  if (!m) return;
  const assunto = (m.assunto || "").toLowerCase().startsWith("re:") ? m.assunto : "Re: " + (m.assunto || "");
  const pronto = mail.rascunho && mail.rascunho.uid === m.uid ? mail.rascunho.rascunho : "";
  mail.exResp = { uid: m.uid, para: m.de_email, assunto, corpo: comRascunho ? pronto : "", estado: comRascunho && !pronto ? "preparando" : "escrevendo" };
  mail.exRespEntra = m.uid;
  mail.exRespRolar = true;
  desenharEmail();
  if (mail.exResp.estado !== "preparando") return;
  let r;
  try {
    r = await fetch("/api/email/rascunho", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ uid: m.uid, conta_id: mail.conta ? mail.conta.id : "" }) });
  } catch (err) { r = null; avisoCert(String(err)); }
  if (!mail.exResp || mail.exResp.uid !== m.uid) return;
  if (!r || !r.ok) { if (r) avisoCert(await erroDe(r)); mail.exResp.estado = "escrevendo"; }
  else {
    const d = await r.json();
    mail.rascunho = Object.assign({ uid: m.uid }, d);
    Object.assign(mail.exResp, { corpo: d.rascunho, assunto: d.assunto || mail.exResp.assunto, estado: "escrevendo" });
  }
  mail.exRespRolar = true;
  desenharEmail();
}

function exFocarResposta() {
  setTimeout(() => {
    const t = $("ex-resp-texto");
    if (!t) return;
    t.focus();
    t.setSelectionRange(t.value.length, t.value.length);
    t.style.height = "auto"; t.style.height = Math.max(150, t.scrollHeight) + "px";
  }, 0);
}

async function exEnviarResposta() {
  const r = mail.exResp;
  if (!r || !r.corpo.trim()) { avisoCert("escreva a resposta antes de enviar"); exFocarResposta(); return; }
  r.estado = "enviando";
  desenharEmail();
  const d = await exMandar({ conta_id: mail.conta ? mail.conta.id : "", para: r.para, cc: "", cco: "", assunto: r.assunto, corpo: r.corpo, anexos: [] });
  if (!mail.exResp || mail.exResp !== r) return;
  if (!d) { r.estado = "escrevendo"; if (mail.visao === "caixa") desenharEmail(); return; }
  r.estado = "enviado"; r.retorno = d;
  await carregarFilaDeEmail();
  mail.exRespRolar = true;
  if (mail.visao === "caixa") desenharEmail();
}

function exLigarResposta(raiz) {
  const m = mail.aberta;
  const responder = (com) => () => exResponder(com);
  ["mail-responder", "mail-responder-ic"].forEach((id) => { const b = $(id); if (b) b.onclick = responder(false); });
  const comR = $("mail-responder-rascunho");
  if (comR) comR.onclick = responder(true);
  const aprovar = $("mail-aprovar-enviar");
  if (aprovar && mail.conta && mail.conta.por_login) aprovar.onclick = async () => {
    const x = mail.rascunho;
    if (!x) return;
    const d = await exMandar({ conta_id: mail.conta.id, para: x.para.join(", "), cc: "", cco: "", assunto: x.assunto, corpo: x.rascunho, anexos: [] });
    if (!d) return;
    mail.rascunho = null;
    avisoCert(d.aguardando_aprovacao ? "o envio parou na fila de Aprovações · nada sai sem o seu sim" : "enviado para " + (d.para || []).join(", "));
    await carregarFilaDeEmail();
    desenharEmail();
  };
  const r = mail.exResp;
  if (!r || !m || r.uid !== m.uid) return;
  const texto = $("ex-resp-texto");
  let relogio;
  if (texto) {
    texto.style.height = "auto"; texto.style.height = Math.max(150, texto.scrollHeight) + "px";
    texto.oninput = () => {
      r.corpo = texto.value;
      texto.style.height = "auto"; texto.style.height = Math.max(150, texto.scrollHeight) + "px";
      clearTimeout(relogio);
      relogio = setTimeout(() => { const alvo = $("ex-resp-conferi"); if (alvo) alvo.innerHTML = exConferir(r, m); }, 500);
    };
  }
  const assunto = $("ex-resp-assunto");
  if (assunto) assunto.oninput = () => { r.assunto = assunto.value; };
  raiz.querySelectorAll("[data-ex-resp-descartar]").forEach((b) => { b.onclick = () => { mail.exResp = null; desenharEmail(); }; });
  raiz.querySelectorAll("[data-ex-resp-fechar]").forEach((b) => { b.onclick = () => { mail.exResp = null; desenharEmail(); }; });
  raiz.querySelectorAll("[data-ex-resp-cheia]").forEach((b) => { b.onclick = () => { const x = mail.exResp; mail.exResp = null; telaEscrever({ para: x.para, assunto: x.assunto, corpo: x.corpo }); }; });
  raiz.querySelectorAll("[data-ex-resp-rascunho]").forEach((b) => { b.onclick = () => exResponder(true); });
  raiz.querySelectorAll("[data-ex-resp-enviar]").forEach((b) => { b.onclick = exEnviarResposta; });
}

/* ------------------------------------------------ abrir na propria lista */
/*
   Na caixa inteira de "a", a mensagem abre no lugar da linha, sem trocar o
   cartao. ?lista_abre=lugar (a mensagem inteira) ou espiada (tres linhas,
   o prazo e as acoes rapidas; "Ler inteira" leva ao cartao). Setas ou j/k
   passam de uma para a outra; Esc fecha.
*/

function exAbreNaLista() {
  return desenhoDaCaixa() === "a" && exModo() === "lista" && exNaCaixa();
}

function exJeitoDeAbrir() {
  return new URLSearchParams(location.search).get("lista_abre") === "espiada" ? "espiada" : "lugar";
}

function exDentro(m) {
  const cheia = mail.aberta && mail.aberta.uid === m.uid ? mail.aberta : null;
  const entra = mail.exAnimar === m.uid ? " entra" : "";
  const c = mail.conta;
  const fechar = '<button class="ex-fechar" data-ex-fechar="1" title="Fechar (Esc)" aria-label="Fechar">' + ic("close", 18) + "</button>";
  if (!cheia) {
    return '<div class="ex-dentro' + entra + '"><div class="ex-dentro-topo"><span>' + esc(m.de_email || "") + "</span>" + fechar + "</div>" +
      '<p class="ex-corpo ex-abrindo">' + (mail.exFalhou === m.uid ? "Não consegui abrir esta mensagem." : "abrindo…") + "</p></div>";
  }
  if (exJeitoDeAbrir() === "espiada") {
    if (exRespAtiva(cheia)) {
      return '<div class="ex-dentro espiada' + entra + '"><p class="ex-espiada">' + esc(cheia.corpo || "(mensagem sem texto)") + "</p>" + exResposta(cheia, false) + "</div>";
    }
    return '<div class="ex-dentro espiada' + entra + '"><p class="ex-espiada">' + esc(cheia.corpo || "(mensagem sem texto)") + "</p>" +
      (cheia.prazo ? '<p class="ex-espiada-prazo">' + ic("event_upcoming", 15) + "<b>Prazo " + esc(dataCurta(cheia.prazo)) + "</b>" +
        (cheia.prazo_trecho ? "<span>“" + esc(cheia.prazo_trecho) + "”</span>" : "") + '<button class="sv-ligacao" data-em-prazo="agenda">Criar na Agenda</button></p>' : "") +
      ((cheia.anexos || []).length ? '<p class="ex-espiada-anexos">' + ic("attach_file", 15) + esc(cheia.anexos.map((a) => a.nome).join(", ")) + "</p>" : "") +
      '<div class="ex-dentro-acoes"><button class="primario com-icone" id="mail-responder">' + ic("reply", 16) + "Responder</button>" +
      '<button class="com-icone" data-ex-arquivar-lista="1">' + ic("archive", 16) + "Arquivar</button>" +
      '<button class="com-icone" data-ex-ler="1">' + ic("fullscreen", 16) + "Ler inteira</button>" +
      '<span class="cresce"></span><span class="ex-teclas">↑ ↓ passa · Esc fecha</span>' + fechar + "</div></div>";
  }
  return '<div class="ex-dentro' + entra + '"><div class="ex-dentro-topo"><span>' + esc(cheia.de_email) + (c ? " · para " + esc(c.email) : "") + "</span>" +
    exIcones(false) + fechar + "</div>" +
    exCorpoMsg(cheia) + (exRespAtiva(cheia) ? exResposta(cheia, false) + "</div>" : exNotas(cheia) +
    '<div class="ex-dentro-acoes"><button class="primario com-icone" id="mail-responder">' + ic("reply", 16) + "Responder</button>" +
    (cheia.pode_rascunhar ? '<button class="com-icone" id="mail-responder-rascunho">' + ic("auto_awesome", 16) + "Com o rascunho</button>" : "") +
    '<span class="cresce"></span><span class="ex-teclas">↑ ↓ passa · Esc fecha</span></div></div>');
}

/* Abre a mensagem pela rota de sempre; se nao vier, a tela diz, em vez de
   ficar em "abrindo…". */
function exAbrirMensagem(uid) {
  mail.exFalhou = null;
  return abrirMensagem(uid).catch(() => {}).then(() => {
    if (!mail.aberta || mail.aberta.uid !== uid) {
      mail.exFalhou = uid;
      if (mail.visao === "caixa") desenharEmail();
    }
  });
}

function exAbrirNaLista(uid) {
  if (!uid) return;
  if (mail.exLinhaAberta === uid) { exFecharNaLista(); return; }
  mail.exLinhaAberta = uid; mail.exAnimar = uid; mail.exLer = false;
  mail.aberta = null;
  desenharEmail();
  exAbrirMensagem(uid).then(() => { if (mail.exLinhaAberta === uid) exMostrarAberta(uid); });
}

/* Chegou a mensagem: se ela passa do fundo, sobe o que falta, sem deixar a
   linha dela sair por cima. */
function exMostrarAberta(uid) {
  const rolagem = document.querySelector("#email .sv-principal");
  const linha = document.querySelector('#email [data-ex-abre="' + uid + '"]');
  const item = linha && linha.closest(".ex-item");
  if (!rolagem || !item) return;
  const r = rolagem.getBoundingClientRect(), l = linha.getBoundingClientRect(), i = item.getBoundingClientRect();
  const sobra = i.bottom - r.bottom + 24;
  if (sobra > 0) rolagem.scrollTop += Math.max(0, Math.min(sobra, l.top - r.top - 72));
}

function exFecharNaLista() {
  mail.exLinhaAberta = null; mail.aberta = null; mail.exLer = false;
  desenharEmail();
}

function exPassarNaLista(passo) {
  const uids = [...document.querySelectorAll("#email [data-ex-abre]")].map((b) => b.dataset.exAbre);
  if (!uids.length) return;
  const i = uids.indexOf(mail.exLinhaAberta);
  const j = i < 0 ? (passo > 0 ? 0 : uids.length - 1) : Math.min(uids.length - 1, Math.max(0, i + passo));
  if (uids[j] !== mail.exLinhaAberta) exAbrirNaLista(uids[j]);
}

/* Traz a resposta inteira para a vista (sem scrollIntoView): sobe o que
   passar do fundo, sem deixar o topo dela sair por cima. */
function exMostrarResposta() {
  const rolagem = document.querySelector("#email .sv-principal");
  const caixa = document.querySelector("#email .ex-resp");
  if (!rolagem || !caixa) return;
  const r = rolagem.getBoundingClientRect(), c = caixa.getBoundingClientRect();
  const sobra = c.bottom - r.bottom + 24;
  if (sobra > 0) rolagem.scrollTop += Math.min(sobra, c.top - r.top - 16);
  else if (c.top < r.top) rolagem.scrollTop += c.top - r.top - 16;
}

/* Traz a linha aberta para a vista, sem scrollIntoView. */
function exMostrarLinha(uid) {
  const rolagem = document.querySelector("#email .sv-principal");
  const linha = document.querySelector('#email [data-ex-abre="' + uid + '"]');
  if (!rolagem || !linha) return;
  const r = rolagem.getBoundingClientRect(), l = linha.getBoundingClientRect();
  if (l.top < r.top + 12 || l.top > r.bottom - 160) rolagem.scrollTop += l.top - r.top - 72;
}

document.addEventListener("keydown", (ev) => {
  if (!document.querySelector("#email.ex-tela") || !exAbreNaLista() || mail.exLer) return;
  if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
  const alvo = ev.target;
  if (alvo && (alvo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName))) return;
  if (document.querySelector(".menu-conversa.menu-novo")) return;
  if (mail.exResp && mail.exResp.uid === mail.exLinhaAberta && mail.exResp.estado !== "enviado") return;
  if (ev.key === "ArrowDown" || ev.key === "j") { ev.preventDefault(); exPassarNaLista(1); }
  else if (ev.key === "ArrowUp" || ev.key === "k") { ev.preventDefault(); exPassarNaLista(-1); }
  else if (ev.key === "Escape" && mail.exLinhaAberta) { ev.preventDefault(); exFecharNaLista(); }
});

/* --------------------------------------------------------- desenho */

function exDesenhar() {
  const d = desenhoDaCaixa();
  cabecalhoEmail();
  const ab = exAbreNaLista() && !mail.exLer ? "" : mail.aberta ? mail.aberta.uid : mail.envioAberto !== null ? "e" + mail.envioAberto : mail.pedidoAberto || "";
  const chave = [d, mail.pasta, exModo(), ab, mail.exIndice || 0, mail.exLer ? "ler" : ""].join(":");
  const antes = document.querySelector("#email .sv-principal");
  const topo = antes ? antes.scrollTop : 0;
  let miolo;
  if (!mail.conta) {
    miolo = '<section class="ec-cartao"><div class="ec-marca"><img src="img/paulus-logo.png" alt=""><span>PAULUS · E-mail</span></div><h2>Nenhuma conta conectada</h2>' +
      '<p class="ec-lide">Entre com a sua conta para ver a caixa de entrada.</p>' +
      '<div class="ec-botoes"><button class="primario" data-em-visao="contas">Entrar em uma conta</button></div></section>' + ecRegras();
  } else if (d === "a" && exModo() === "fila" && mail.pasta === "entrada") {
    miolo = exCartaoFila();
  } else if (d === "c") {
    miolo = '<div class="ex-folhas">' + exCartaoLista() + (exAlgoAberto() && exCartaoAberto(false) ? exCartaoAberto(false)
      : '<section class="ec-cartao ex-cartao ex-nada"><span class="sv-kicker">Nada aberto</span><h2>Escolha uma mensagem</h2>' +
        '<p class="ec-lide">Eu leio a mensagem só quando você abre. Até lá ela fica no seu servidor, por isso a lista abre rápido.</p></section>') + "</div>" + ecRegras();
  } else {
    const volta = d === "a" ? '<button class="sv-ligacao ex-volta-fila" data-ex-modo="fila">' + ic("arrow_back", 15) + "Voltar para a fila</button>" : "";
    const cheio = exAbreNaLista() ? mail.exLer && mail.aberta : exAlgoAberto() && exCartaoAberto(true);
    miolo = (cheio ? exCartaoAberto(true) : exCartaoLista(volta)) + ecRegras();
  }
  const classe = "acervo sem-painel ec-tela ex-tela ex-desenho-" + d;
  $("centro").innerHTML = '<div class="' + classe + '" id="email"><div class="acervo-principal sv-principal"><div class="ec-palco">' + miolo + "</div></div></div>";
  ligarEmail();
  exLigar();
  const novo = document.querySelector("#email .sv-principal");
  if (novo && chave === exChave) novo.scrollTop = topo;
  exChave = chave;
  if (mail.exAnimar) { const u = mail.exAnimar; mail.exAnimar = null; exMostrarLinha(u); }
  if (mail.exRespEntra && mail.exResp && mail.exResp.estado !== "preparando") mail.exRespEntra = null;
  if (mail.exRespRolar && mail.exResp) {
    mail.exRespRolar = false;
    exMostrarResposta();
    if (mail.exResp.estado === "escrevendo") exFocarResposta();
  }
  const pedeResp = new URLSearchParams(location.search).get("resp");
  if (pedeResp && !mail.exRespUrl && mail.aberta) {
    mail.exRespUrl = true;
    if (pedeResp === "enviado") {
      const m = mail.aberta;
      mail.exResp = { uid: m.uid, para: m.de_email, assunto: "Re: " + (m.assunto || ""), corpo: "", estado: "enviado", retorno: { aguardando_aprovacao: true } };
      mail.exRespRolar = true;
      setTimeout(desenharEmail, 0);
    } else setTimeout(() => exResponder(pedeResp === "rascunho"), 0);
  }
  if (exAbreNaLista() && !mail.exUrlLido) {
    mail.exUrlLido = true;
    const u = new URLSearchParams(location.search).get("lista_uid");
    if (u) { mail.exLinhaAberta = u; exAbrirMensagem(u); }
  }
  if (d === "a" && exModo() === "fila" && mail.pasta === "entrada" && mail.conta && !mail.erroCaixa) {
    const item = exFila()[mail.exIndice || 0];
    if (item && (!mail.aberta || mail.aberta.uid !== item.uid) && mail.exAbrindo !== item.uid && mail.exFalhou !== item.uid) {
      mail.exAbrindo = item.uid;
      exAbrirMensagem(item.uid).finally(() => { mail.exAbrindo = null; });
    }
  }
}

/* Troca de conta pelo seletor do alto do cartao. Conta que precisa entrar
   de novo vai para a Contas; as outras abrem a caixa aqui mesmo. */
async function exTrocarConta(c) {
  if (exPrecisaEntrar(c)) return exEntrarDeNovo(c);
  Object.assign(mail, { conta: c, pasta: "entrada", aberta: null, envioAberto: null, pedidoAberto: null, exFila: null, exIndice: 0,
    exResp: null, exLinhaAberta: null, exFalhou: null, exLer: false, rascunho: null });
  await carregarPasta();
  if (mail.visao === "caixa") desenharEmail();
}

function exLigar() {
  const raiz = $("email");
  const redesenhar = () => desenharEmail();
  exLigarResposta(raiz);
  /* A pasta muda por 18-email.js (ligarCaixa); a linha aberta e a resposta
     daqui nao atravessam de uma pasta para a outra. */
  raiz.querySelectorAll("[data-em-pasta]").forEach((b) => {
    const antes = b.onclick;
    b.onclick = (ev) => { mail.exLinhaAberta = null; mail.exResp = null; mail.exLer = false; return antes ? antes.call(b, ev) : undefined; };
  });
  raiz.querySelectorAll("[data-ex-voltar]").forEach((b) => {
    b.onclick = () => {
      if (mail.exLer) { mail.exLer = false; redesenhar(); return; }
      mail.aberta = null; mail.envioAberto = null; mail.pedidoAberto = null; redesenhar();
    };
  });
  raiz.querySelectorAll("[data-ex-abre]").forEach((b) => { b.onclick = () => exAbrirNaLista(b.dataset.exAbre); });
  raiz.querySelectorAll("[data-ex-fechar]").forEach((b) => { b.onclick = exFecharNaLista; });
  raiz.querySelectorAll("[data-ex-ler]").forEach((b) => { b.onclick = () => { mail.exLer = true; redesenhar(); }; });
  const arquivar = async (uid) => {
    let r;
    try {
      r = await fetch("/api/email/arquivar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ uid: uid, conta_id: mail.conta ? mail.conta.id : "" }) });
    } catch (err) { avisoCert(String(err)); return false; }
    if (!r.ok) { avisoCert(await erroDe(r)); return false; }
    const d = await r.json();
    avisoCert(d.aviso || "arquivada · continua no servidor, na pasta de arquivo");
    return true;
  };
  raiz.querySelectorAll("[data-ex-arquivar-lista]").forEach((b) => {
    b.onclick = async () => {
      const m = mail.aberta;
      if (!m || !(await arquivar(m.uid))) return;
      exPassarNaLista(1);
    };
  });
  raiz.querySelectorAll("[data-ex-modo]").forEach((b) => {
    b.onclick = async () => {
      mail.exModo = b.dataset.exModo; mail.aberta = null; mail.exLinhaAberta = null; mail.exLer = false;
      if (mail.exModo === "fila" && mail.pasta !== "entrada") { mail.pasta = "entrada"; await carregarPasta(); }
      redesenhar();
    };
  });
  const irPara = (i) => { mail.exIndice = i; mail.aberta = null; mail.exResp = null; mail.exFalhou = null; redesenhar(); };
  raiz.querySelectorAll("[data-ex-depois]").forEach((b) => { b.onclick = () => irPara((mail.exIndice || 0) + 1); });
  raiz.querySelectorAll("[data-ex-ir]").forEach((b) => { b.onclick = () => irPara(Number(b.dataset.exIr)); });
  raiz.querySelectorAll("[data-ex-recomecar]").forEach((b) => { b.onclick = () => irPara(0); });
  raiz.querySelectorAll("[data-ex-tentar-msg]").forEach((b) => { b.onclick = () => { mail.exFalhou = null; redesenhar(); }; });
  const arquivarFila = raiz.querySelector("[data-ex-arquivar]");
  if (arquivarFila && mail.aberta) arquivarFila.onclick = async () => {
    arquivarFila.disabled = true;
    if (!(await arquivar(mail.aberta.uid))) { arquivarFila.disabled = false; return; }
    irPara((mail.exIndice || 0) + 1);
  };
  raiz.querySelectorAll("[data-ex-tentar]").forEach((b) => {
    b.onclick = async () => { b.disabled = true; await carregarPasta(); redesenhar(); };
  });
  raiz.querySelectorAll("[data-ex-entrar]").forEach((b) => { b.onclick = () => exEntrarDeNovo(mail.conta); });
  const conta = raiz.querySelector("[data-ex-conta]");
  if (conta) conta.onclick = (ev) => {
    ev.stopPropagation();
    menuNaLinha(conta, mail.contas.contas.map((c) => ({
      atual: !!(mail.conta && c.id === mail.conta.id),
      rotulo: c.email + (exPrecisaEntrar(c) ? " · entrar de novo" : ""),
      acao: () => exTrocarConta(c),
    })).concat(["-", { rotulo: "Gerenciar contas", acao: () => mostrarEmail("contas") }]));
  };
}

(function () {
  const desenharAntes = desenharEmail;
  window.desenharEmail = function () {
    if (mail.visao !== "caixa") return desenharAntes();
    exDesenhar();
  };
})();
