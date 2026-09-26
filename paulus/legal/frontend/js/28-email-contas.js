/* ------------------------------------------------------ e-mail: contas */
/*
   Contas de e-mail (B1) em passos, uma pergunta por vez:
     lista       as contas desta maquina
     entrar      "Entrar com Google/Microsoft" - o caminho principal; so
                 existe quando o PAULUS traz algum login (mail.contas.oauth)
     email       outro provedor: endereco, servidor (detectado pelo dominio,
                 ou a mao) e senha, num passo so
     senha       entrar de novo numa conta que ja existe (so a senha)
     manter      guardar a senha nesta maquina, nome e assinatura
   Sem nenhum login de provedor configurado, "email" vira o caminho normal.
   Troca so a visao "contas" de js/18-email.js; as rotas sao as mesmas
   (/api/email/contas, /detectar, /testar, /contas/senha, /usar,
   /esquecer-senhas). ?contas_passo=lista|entrar|email|senha|manter|reconectar
   abre num passo, para revisar o desenho.

   Entrar de novo vai direto a /api/email/contas/senha: a rota ja prova a
   senha contra o servidor da conta guardada, e /testar com so o id e o
   endereco nao sabe o servidor.

   Os botoes do provedor (botoesDeLoginOAuth/ligarLoginOAuth) moram em
   js/30-email-oauth.js; se nao estiverem carregados, fica o caminho da senha.
   js/29-email-caixa.js usa ecEstado, ecNovo, ecRegras e ecContaLigada.
*/

function ecNovo() {
  return { passo: "", email: "", senha: "", nome: "", assinatura: "", deteccao: null, deteccaoDe: "", detectando: false, manual: false, prova: null, erro: "", ocupado: false,
    reconectar: null, abrirDepois: false, padrao: false, guardar: true, imap: "", imapPorta: 993, smtp: "", smtpPorta: 587, ajudaAberta: false, mostrar: false };
}

function ecEstado() {
  if (mail.ec) return mail.ec;
  const e = (mail.ec = ecNovo());
  const p = new URLSearchParams(location.search).get("contas_passo");
  if (p === "email" || p === "lista" || p === "entrar") e.passo = p;
  if (p === "senha") { e.passo = "email"; e.email = "voce@gmail.com"; }
  if (p === "manter") { e.passo = p; e.email = "voce@gmail.com"; e.senha = "abcd efgh ijkl mnop"; e.prova = { entrada: true, saida: true }; }
  if (p === "reconectar") {
    const c = mail.contas.contas.find((x) => x.ultimo_erro && !x.por_login) || mail.contas.contas.find((x) => !x.tem_senha && !x.por_login);
    if (c) { e.passo = "senha"; e.reconectar = c; e.email = c.email; e.abrirDepois = true; }
  }
  return e;
}

function ecTemOAuth() {
  return typeof botoesDeLoginOAuth === "function" && Boolean(botoesDeLoginOAuth());
}

/* Onde comeca uma conta nova: no login do provedor, se houver; senao, no endereco. */
function ecComeco() {
  return ecTemOAuth() ? "entrar" : "email";
}

function ecPasso() {
  const e = ecEstado();
  if (e.passo === "entrar" && !ecTemOAuth()) return "email";
  return e.passo || (mail.contas.contas.length ? "lista" : ecComeco());
}

/* Uma resposta que chega depois de a pessoa ter saido da tela nao redesenha
   por cima da tela nova. */
function ecNaTela() {
  return mail.visao === "contas" && !!document.querySelector("#email.ec-tela");
}

function ecRegras() {
  return '<div class="ec-regras"><span>Leio só o que você abre</span><span>Prazos viram sugestão na Agenda</span><span>Nada sai sem passar por Aprovações</span></div>';
}

function ecQuem(e, volta) {
  return '<button class="ec-quem" data-ee-passo="' + volta + '" title="Voltar">' + ic("arrow_back", 16) + avatarDaConta({ email: e.email }) + "<span>" + esc(e.email) + "</span></button>";
}

function ecErro(e) {
  return e.erro ? '<p class="ec-erro">' + ic("error", 16) + "<span>" + esc(e.erro) + "</span></p>" : "";
}

function ecEmailValido(v) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v);
}

function ecCampoSenha(e) {
  return '<label class="ec-campo"><span class="sv-kicker">Senha</span><span class="ec-senha"><input type="' + (e.mostrar ? "text" : "password") + '" id="ee-senha" value="' + esc(e.senha) + '" placeholder="••••••••" autocomplete="current-password">' +
    '<button class="sv-ligacao" id="ee-mostrar">' + (e.mostrar ? "esconder" : "mostrar") + "</button></span></label>";
}

/* O servidor do passo "email": nada antes do endereco; depois, o que a
   deteccao achou (com "mudar") ou os quatro campos. */
function ecServidor(e) {
  const d = e.deteccaoDe === e.email.trim() ? e.deteccao : null;
  if (e.manual) {
    return '<div class="ec-manual">' +
      '<label class="ec-campo"><span class="sv-kicker">IMAP · ler</span><input type="text" id="ee-imap" value="' + esc(e.imap) + '" placeholder="imap.dominio.com.br"></label>' +
      '<label class="ec-campo"><span class="sv-kicker">Porta</span><input type="text" inputmode="numeric" id="ee-imap-porta" value="' + esc(e.imapPorta) + '"></label>' +
      '<label class="ec-campo"><span class="sv-kicker">SMTP · enviar</span><input type="text" id="ee-smtp" value="' + esc(e.smtp) + '" placeholder="smtp.dominio.com.br"></label>' +
      '<label class="ec-campo"><span class="sv-kicker">Porta</span><input type="text" inputmode="numeric" id="ee-smtp-porta" value="' + esc(e.smtpPorta) + '"></label></div>' +
      (d && !d.achou ? '<p class="ec-nota">' + esc(maiuscula(d.motivo || "não achei o servidor")) + ". Seu provedor informa esses endereços.</p>" : "");
  }
  if (e.detectando) return '<div class="ec-servidor">' + ic("lan", 15) + "<span>procurando o servidor…</span></div>";
  if (!d || !d.achou) return "";
  return '<div class="ec-servidor">' + ic("lan", 15) + "<span>" + esc(d.imap_host + " · " + d.smtp_host) + "</span>" +
    '<button class="sv-ligacao" id="ee-manual">mudar</button></div>';
}

/* O resultado da prova, numa linha so, com o que fazer. */
function ecProva(e) {
  const r = e.prova;
  if (!r || !r.entrada || r.saida) return "";
  return '<p class="ec-erro">' + ic("error", 16) + "<span>Lê, mas não envia: " + esc(r.erro_saida || "o servidor recusou") +
    '. <button class="sv-ligacao" id="ee-continuar">seguir assim mesmo</button></span></p>';
}

function ecVolta(destino) {
  return destino ? '<button class="sv-ligacao" data-ee-passo="' + destino + '">Voltar</button>' : "";
}

function ecCartao() {
  const e = ecEstado();
  const passo = ecPasso();
  const contas = mail.contas.contas;
  let corpo = "";
  if (passo === "lista") {
    const alguma = contas.some((c) => c.tem_senha);
    corpo = "<h2>Contas</h2>" +
      '<div class="ec-lista">' + contas.map((c) => {
        const linha = c.por_login && (c.precisa_entrar || !c.tem_senha) ? "Login " + (c.rotulo_autenticacao || "").replace("login ", "") + " vencido · entre de novo"
          : c.por_login && c.ultimo_erro ? "Não conectou · " + c.ultimo_erro
          : c.ultimo_erro ? "Senha recusada · entre de novo"
          : (c.em_uso ? "Envia por padrão · " : "") +
            (c.tem_senha ? (c.quando_ok ? "sincronizada " + c.quando_ok : "ainda não sincronizada") : "senha não guardada");
        return '<div class="ec-conta' + (c.ultimo_erro ? " problema" : "") + (c.em_uso ? " padrao" : "") + '"><button class="ec-conta-botao" data-ee-abrir="' + esc(c.id) + '">' +
          avatarDaConta(c, true) + '<span class="ec-conta-texto"><b>' + esc(c.email) + "</b><small>" + esc(linha) + "</small></span></button>" +
          '<button class="ec-mais" data-ee-mais="' + esc(c.id) + '" title="Mais" aria-label="Mais">' + ic("more_vert", 18) + "</button></div>";
      }).join("") +
      '<button class="ec-conta-botao ec-outra" data-ee-passo="' + ecComeco() + '"><span class="ec-mais-ic">' + ic("add", 20) + '</span><span class="ec-conta-texto"><b>Adicionar conta</b></span></button></div>' +
      (alguma ? '<div class="ec-pe"><button class="sv-ligacao" id="mail-esquecer">Apagar os acessos guardados</button></div>' : "");
  } else if (passo === "entrar") {
    /* O login do provedor na frente; a senha (IMAP/SMTP) fica num link discreto. */
    corpo = "<h2>Entrar no e-mail</h2>" + botoesDeLoginOAuth() +
      '<div class="ec-pe ec-pe-entrar">' + ecVolta(contas.length ? "lista" : "") +
      '<button class="sv-ligacao" data-ee-passo="email">Outro provedor (IMAP e SMTP)</button></div>';
  } else if (passo === "email") {
    const d = e.deteccaoDe === e.email.trim() ? e.deteccao : null;
    const volta = ecTemOAuth() ? "entrar" : contas.length ? "lista" : "";
    corpo = "<h2>" + (ecTemOAuth() ? "IMAP e SMTP" : "Entrar no e-mail") + "</h2>" +
      '<label class="ec-campo"><span class="sv-kicker">E-mail</span><input type="email" id="ee-email" value="' + esc(e.email) + '" placeholder="nome@dominio.com.br" autocomplete="email"></label>' +
      ecCampoSenha(e) +
      (d && d.aviso ? '<div class="ec-aviso"><b>Esta conta não funciona aqui</b><p>' + esc(d.aviso) + "</p></div>" : "") +
      (d && d.ajuda ? '<details class="ec-ajuda"' + (e.ajudaAberta ? " open" : "") + "><summary>Senha de app</summary><p>" + esc(d.ajuda) + "</p></details>" : "") +
      ecServidor(e) +
      ecErro(e) + ecProva(e) +
      '<div class="ec-botoes">' + ecVolta(volta) + '<button class="primario" id="ee-entrar"' + (e.ocupado ? " disabled" : "") + ">" + (e.ocupado ? "Conferindo…" : "Entrar") + "</button></div>";
  } else if (passo === "senha") {
    /* Entrar de novo numa conta que ja existe: so a senha. */
    const c = e.reconectar || {};
    corpo = ecQuem(e, "lista") +
      "<h2>Entrar de novo</h2>" +
      '<p class="ec-lide">' + (c.ultimo_erro ? "O servidor recusou a senha guardada." : "Não há senha guardada nesta máquina.") + "</p>" +
      ecCampoSenha(e) +
      ecErro(e) +
      '<div class="ec-botoes"><button class="primario" id="ee-entrar"' + (e.ocupado ? " disabled" : "") + ">" + (e.ocupado ? "Conferindo…" : "Entrar") + "</button></div>";
  } else {
    const pode = mail.contas.pode_guardar_senha;
    corpo = ecQuem(e, "email") +
      "<h2>" + (pode ? "Guardar a senha?" : "Quase pronto") + "</h2>" +
      '<p class="ec-lide">' + (pode ? "Cifrada pela sua conta do Windows. Sem guardar, ela vale até fechar o programa."
        : "Este sistema não guarda senha com segurança: ela vale até fechar o programa.") + "</p>" +
      '<label class="ec-campo"><span class="sv-kicker">Seu nome, para quem recebe</span><input type="text" id="ee-nome" value="' + esc(e.nome) + '" placeholder="Nome e sobrenome"></label>' +
      '<label class="ec-campo"><span class="sv-kicker">Assinatura · opcional</span><textarea id="ee-assinatura" placeholder="Nome · OAB/UF 00000">' + esc(e.assinatura) + "</textarea></label>" +
      '<div class="ag-toggle' + (e.padrao ? " on" : "") + '" data-ee-padrao="1"><span>Conta padrão de envio</span><i></i></div>' +
      ecErro(e) +
      '<div class="ec-botoes">' + (pode ? '<button data-ee-guardar="nao">Não guardar</button><button class="primario" data-ee-guardar="sim">Guardar</button>'
        : '<button class="primario" data-ee-guardar="nao">Concluir</button>') + "</div>";
  }
  return '<section class="ec-cartao" data-passo="' + passo + '"><div class="ec-marca"><img src="img/paulus-icone.svg" alt=""><span>PAULUS · E-mail</span></div>' + corpo + "</section>";
}

/* Depois de redesenhar, o cursor volta ao campo em que estava; sem isso, ao
   primeiro campo vazio do passo. */
function ecFoco(antes) {
  setTimeout(() => {
    const ids = ["ee-email", "ee-senha", "ee-nome"];
    let campo = antes && $(antes);
    if (!campo) campo = ids.map((id) => $(id)).find((x) => x && !x.value) || ids.map((id) => $(id)).find(Boolean);
    if (!campo) return;
    campo.focus();
    try { const n = campo.value.length; campo.setSelectionRange(n, n); } catch (err) { /* type=email nao deixa */ }
  }, 0);
}

function ecRedesenhar() {
  const ativo = document.activeElement && document.activeElement.id && document.activeElement.id.startsWith("ee-") ? document.activeElement.id : "";
  desenharEmail();
  ecFoco(ativo);
}

async function ecDetectar() {
  const e = ecEstado();
  const alvo = e.email.trim();
  let d;
  try {
    d = await (await fetch("/api/email/detectar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: alvo }) })).json();
  } catch (err) { d = { achou: false, motivo: String(err) }; }
  if (e.email.trim() !== alvo) return;
  e.deteccao = d;
  e.deteccaoDe = alvo;
  if (d.achou) { e.imap = d.imap_host; e.imapPorta = d.imap_porta; e.smtp = d.smtp_host; e.smtpPorta = d.smtp_porta; e.manual = false; }
  else e.manual = true;
}

/* O endereco mudou e esta completo: descobre o servidor enquanto a pessoa
   digita a senha. Nao redesenha no comeco - o "change" vem no mousedown de
   quem ja clicou em Entrar, e trocar o botao ali engoliria o clique - nem no
   fim, se Entrar ja estiver cuidando disso. */
async function ecDetectarAgora() {
  const e = ecEstado();
  const v = e.email.trim();
  if (!ecEmailValido(v) || e.deteccaoDe === v || e.detectando) return;
  e.detectando = true;
  await ecDetectar();
  e.detectando = false;
  if (ecNaTela() && ecPasso() === "email" && !e.ocupado) ecRedesenhar();
}

function ecFicha() {
  const e = ecEstado();
  return { email: e.email.trim(), nome: e.nome.trim(), imap_host: e.imap.trim(), imap_porta: Number(e.imapPorta) || 993, smtp_host: e.smtp.trim(), smtp_porta: Number(e.smtpPorta) || 587,
    guardar_senha: e.guardar !== false, assinatura: e.assinatura.trim() };
}

/* Entrar de novo: a rota prova a senha contra o servidor da conta guardada e
   so entao a aceita. */
async function ecReconectar() {
  const e = ecEstado();
  const c = e.reconectar;
  e.ocupado = true; e.erro = "";
  desenharEmail();
  let s;
  try {
    s = await fetch("/api/email/contas/senha", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: c.id, senha: e.senha }) });
  } catch (err) { s = null; e.erro = String(err); }
  e.ocupado = false;
  if (!s || !s.ok) {
    if (s) e.erro = "O servidor não aceitou: " + (await erroDe(s));
    return ecNaTela() ? ecRedesenhar() : undefined;
  }
  mail.contas = await s.json();
  const abrir = e.abrirDepois;
  Object.assign(e, ecNovo(), { passo: "lista" });
  const conta = mail.contas.contas.find((x) => x.id === c.id);
  avisoCert("conta reconectada · " + (conta && conta.tem_senha ? "senha guardada" : "a senha vale até fechar o programa"));
  if (abrir && conta) { mail.conta = conta; return carregarCaixa(); }
  if (ecNaTela()) desenharEmail();
}

async function ecEntrar() {
  const e = ecEstado();
  if (e.ocupado) return;
  if (e.reconectar) {
    if (!e.senha) { e.erro = "Digite a senha."; return ecRedesenhar(); }
    return ecReconectar();
  }
  const v = e.email.trim();
  if (!ecEmailValido(v)) { e.erro = "Digite o endereço completo, como nome@dominio.com.br."; return ecRedesenhar(); }
  if (mail.contas.contas.some((c) => c.email.toLowerCase() === v.toLowerCase())) { e.erro = "Esta conta já está na lista."; return ecRedesenhar(); }
  e.erro = "";
  if (e.deteccaoDe !== v) {
    e.ocupado = true;
    ecRedesenhar();
    await ecDetectar();
    e.ocupado = false;
    if (!ecNaTela()) return;
  }
  if (!e.senha) { e.erro = "Digite a senha."; return ecRedesenhar(); }
  if (!e.imap.trim() || !e.smtp.trim()) { e.erro = "Preencha os servidores IMAP e SMTP."; e.manual = true; return ecRedesenhar(); }
  e.ocupado = true; e.prova = null;
  desenharEmail();
  let r;
  try {
    r = await (await fetch("/api/email/testar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dados: ecFicha(), senha: e.senha }) })).json();
  } catch (err) { r = { ok: false, entrada: false, erro_entrada: String(err) }; }
  e.ocupado = false;
  e.prova = r;
  if (!ecNaTela()) return;
  if (!r.entrada) { e.erro = "Não entrou: " + (r.erro_entrada || "o servidor recusou a senha") + "."; return ecRedesenhar(); }
  if (!r.saida) return ecRedesenhar();
  e.passo = "manter";
  ecRedesenhar();
}

async function ecGuardar(sim) {
  const e = ecEstado();
  if (e.ocupado) return;
  e.guardar = sim;
  e.ocupado = true;
  let r;
  try {
    r = await fetch("/api/email/contas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dados: ecFicha(), senha: e.senha }) });
  } catch (err) { r = null; e.erro = String(err); }
  e.ocupado = false;
  if (!r || !r.ok) { if (r) e.erro = await erroDe(r); return ecNaTela() ? ecRedesenhar() : undefined; }
  mail.contas = await r.json();
  const alvo = e.email.trim().toLowerCase();
  const nova = mail.contas.contas.find((c) => c.email.toLowerCase() === alvo);
  if (e.padrao && nova) {
    const u = await fetch("/api/email/contas/" + nova.id + "/usar", { method: "POST" });
    if (u.ok) mail.contas = await u.json();
  }
  mail.conta = mail.contas.contas.find((c) => c.email.toLowerCase() === alvo) || mail.conta;
  Object.assign(e, ecNovo(), { passo: "lista" });
  avisoCert("conta conectada · " + (sim ? "senha guardada" : "a senha vale até fechar o programa"));
  carregarCaixa();
}

/* A conta que ligou por fora (entrar com o provedor): recarrego a lista e
   abro a caixa dela, como no fim do fluxo. */
async function ecContaLigada(conta) {
  const e = ecEstado();
  try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { /* mostrarEmail recarrega */ }
  const lista = (mail.contas && mail.contas.contas) || [];
  const achada = conta ? lista.find((c) => (conta.id && c.id === conta.id) || (conta.email && c.email.toLowerCase() === String(conta.email).toLowerCase())) : null;
  if (achada) mail.conta = achada;
  Object.assign(e, ecNovo(), { passo: "lista" });
  avisoCert("conta conectada" + (achada ? " · " + achada.email : ""));
  carregarCaixa();
}

function ecLigarContas() {
  const raiz = $("email");
  const e = ecEstado();
  const reconectar = (c, abrir) => {
    /* Conta que entra pelo login do Google/Microsoft nao tem senha: refaz o login. */
    if (c.por_login && typeof entrarDeNovoOAuth === "function") return entrarDeNovoOAuth(c, ecContaLigada);
    Object.assign(e, ecNovo(), { passo: "senha", reconectar: c, email: c.email, abrirDepois: abrir }); ecRedesenhar();
  };
  raiz.querySelectorAll("[data-ee-passo]").forEach((b) => {
    b.onclick = () => {
      const p = b.dataset.eePasso;
      e.erro = "";
      if (p === "lista" || e.reconectar) Object.assign(e, ecNovo());
      if (p === "email") e.prova = null;
      e.passo = p;
      ecRedesenhar();
    };
  });
  raiz.querySelectorAll("[data-ee-abrir]").forEach((b) => {
    b.onclick = () => {
      const c = mail.contas.contas.find((x) => x.id === b.dataset.eeAbrir);
      if (!c) return;
      if (c.ultimo_erro || !c.tem_senha) return reconectar(c, true);
      mail.conta = c;
      carregarCaixa();
    };
  });
  raiz.querySelectorAll("[data-ee-mais]").forEach((b) => {
    b.onclick = (ev) => {
      ev.stopPropagation();
      const c = mail.contas.contas.find((x) => x.id === b.dataset.eeMais);
      if (!c) return;
      const itens = [];
      if (!c.em_uso) itens.push({ icone: "send", rotulo: "Usar como padrão de envio", acao: async () => {
        mail.contas = await (await fetch("/api/email/contas/" + c.id + "/usar", { method: "POST" })).json();
        desenharEmail();
      } });
      itens.push({ icone: "sync", rotulo: "Entrar de novo", acao: () => reconectar(c, false) });
      itens.push({ icone: "inbox", rotulo: "Abrir a caixa", acao: () => { mail.conta = c; carregarCaixa(); } });
      itens.push("-");
      itens.push({ icone: "delete", rotulo: "Remover", perigo: true, acao: async () => {
        if (!(await confirmar({ titulo: "Remover esta conta?", contexto: "E-mail › Contas › " + c.email, texto: "O acesso guardado nesta máquina é apagado. As mensagens continuam no servidor.", confirmar: "Remover", perigo: true }))) return;
        mail.contas = await (await fetch("/api/email/contas/" + c.id, { method: "DELETE" })).json();
        mail.conta = mail.contas.contas.find((x) => x.em_uso) || mail.contas.contas[0] || null;
        desenharEmail();
      } });
      menuNaLinha(b, itens);
    };
  });
  const esquecer = $("mail-esquecer");
  if (esquecer) esquecer.onclick = async () => {
    if (!(await confirmar({ titulo: "Apagar os acessos guardados?", contexto: "E-mail › Contas", texto: "Senhas e logins saem desta máquina. As contas continuam na lista e pedem para entrar de novo.", confirmar: "Apagar", perigo: true }))) return;
    mail.contas = await (await fetch("/api/email/esquecer-senhas", { method: "POST" })).json();
    desenharEmail();
  };
  const guarda = (id, chave) => { const el = $(id); if (el) el.oninput = () => { e[chave] = el.value; }; return el; };
  [["ee-email", "email"], ["ee-senha", "senha"], ["ee-imap", "imap"], ["ee-imap-porta", "imapPorta"], ["ee-smtp", "smtp"], ["ee-smtp-porta", "smtpPorta"], ["ee-nome", "nome"], ["ee-assinatura", "assinatura"]].forEach(([id, k]) => guarda(id, k));
  /* Endereco novo: sai a prova antiga e procura o servidor dele. */
  const email = $("ee-email");
  if (email) {
    email.oninput = () => { e.email = email.value; if (e.prova) e.prova = null; };
    email.onchange = () => ecDetectarAgora();
  }
  /* Enter em qualquer campo de uma linha faz o que o botao principal do passo faz. */
  raiz.querySelectorAll(".ec-cartao input").forEach((campo) => {
    campo.onkeydown = (ev) => {
      if (ev.key !== "Enter") return;
      ev.preventDefault();
      const principal = raiz.querySelector(".ec-botoes .primario");
      if (principal && !principal.disabled) principal.click();
    };
  });
  const mostrar = $("ee-mostrar");
  if (mostrar) mostrar.onclick = () => { e.mostrar = !e.mostrar; ecRedesenhar(); };
  const manual = $("ee-manual");
  if (manual) manual.onclick = () => { e.manual = true; desenharEmail(); const i = $("ee-imap"); if (i) i.focus(); };
  const entrar = $("ee-entrar");
  if (entrar) entrar.onclick = ecEntrar;
  const continuar = $("ee-continuar");
  if (continuar) continuar.onclick = () => { e.passo = "manter"; ecRedesenhar(); };
  const ajuda = raiz.querySelector(".ec-ajuda");
  if (ajuda) ajuda.ontoggle = () => { e.ajudaAberta = ajuda.open; };
  const padrao = raiz.querySelector("[data-ee-padrao]");
  if (padrao) padrao.onclick = () => { e.padrao = !e.padrao; padrao.classList.toggle("on", e.padrao); };
  raiz.querySelectorAll("[data-ee-guardar]").forEach((b) => { b.onclick = () => ecGuardar(b.dataset.eeGuardar === "sim"); });
  if (ecPasso() === "entrar" && typeof ligarLoginOAuth === "function") {
    const cartao = raiz.querySelector(".ec-cartao");
    if (cartao) ligarLoginOAuth(cartao, ecContaLigada);
  }
  if (ecPasso() === "email" && ecEmailValido(e.email.trim()) && e.deteccaoDe !== e.email.trim() && !e.detectando) ecDetectarAgora();
}

(function () {
  const desenharAntes = desenharEmail;
  window.desenharEmail = function () {
    if (mail.visao !== "contas") return desenharAntes();
    cabecalhoEmail();
    const passo = ecPasso();
    $("centro").innerHTML = '<div class="acervo sem-painel ec-tela" id="email"><div class="acervo-principal sv-principal"><div class="ec-palco">' +
      ecCartao() + (passo === "entrar" || passo === "email" ? ecRegras() : "") + "</div></div></div>";
    ligarEmail();
  };
  window.ligarContas = ecLigarContas;
})();
