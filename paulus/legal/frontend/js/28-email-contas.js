/* ------------------------------------------------------ e-mail: contas */
/*
   Contas de e-mail (B1) como uma entrada em passos, uma pergunta por vez:
   escolher a conta, o endereco, a senha e, por fim, se a senha fica
   guardada. O servidor sai do dominio e so aparece para mexer quando nao
   acho. Troca so a visao "contas" de js/18-email.js; as rotas sao as mesmas
   (/api/email/contas, /detectar, /testar, /contas/senha, /usar,
   /esquecer-senhas). ?contas_passo=lista|email|senha|manter|reconectar abre
   num passo, para revisar o desenho.

   Entrar de novo vai direto a /api/email/contas/senha: a rota ja prova a
   senha contra o servidor da conta guardada, e /testar com so o id e o
   endereco nao sabe o servidor.

   Os botoes de entrar com o provedor (botoesDeLoginOAuth/ligarLoginOAuth)
   moram em outro arquivo; se nao estiverem carregados, o passo do endereco
   fica so com o endereco e a senha.
*/

function ecNovo() {
  return { passo: "", email: "", senha: "", nome: "", assinatura: "", deteccao: null, manual: false, prova: null, erro: "", ocupado: false,
    reconectar: null, abrirDepois: false, padrao: false, guardar: true, imap: "", imapPorta: 993, smtp: "", smtpPorta: 587, ajudaAberta: false, mostrar: false };
}

function ecEstado() {
  if (mail.ec) return mail.ec;
  const e = (mail.ec = ecNovo());
  const p = new URLSearchParams(location.search).get("contas_passo");
  if (p === "email" || p === "lista") e.passo = p;
  if (p === "senha" || p === "manter") { e.passo = p; e.email = "voce@gmail.com"; }
  if (p === "manter") { e.senha = "abcd efgh ijkl mnop"; e.prova = { entrada: true, saida: true }; }
  if (p === "reconectar") {
    const c = mail.contas.contas.find((x) => x.ultimo_erro) || mail.contas.contas.find((x) => !x.tem_senha);
    if (c) { e.passo = "senha"; e.reconectar = c; e.email = c.email; e.abrirDepois = true; }
  }
  return e;
}

function ecPasso() {
  const e = ecEstado();
  return e.passo || (mail.contas.contas.length ? "lista" : "email");
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

function ecOAuth() {
  const botoes = typeof botoesDeLoginOAuth === "function" ? botoesDeLoginOAuth() : "";
  if (!botoes) return "";
  return '<div class="ec-ou"><span>ou</span></div><div class="ec-oauth">' + botoes + "</div>";
}

function ecCartao() {
  const e = ecEstado();
  const passo = ecPasso();
  const contas = mail.contas.contas;
  let corpo = "";
  if (passo === "lista") {
    const alguma = contas.some((c) => c.tem_senha);
    corpo = "<h2>Escolha uma conta</h2>" +
      '<p class="ec-lide">Clique para abrir a caixa. A conta que envia por padrão vem marcada.</p>' +
      '<div class="ec-lista">' + contas.map((c) => {
        const linha = c.por_login && (c.precisa_entrar || !c.tem_senha) ? "Login " + (c.rotulo_autenticacao || "").replace("login ", "") + " vencido · entre de novo"
          : c.por_login && c.ultimo_erro ? "Não conectou · " + c.ultimo_erro
          : c.ultimo_erro ? "Senha recusada · entre de novo"
          : (c.em_uso ? "Envia por padrão · " : "") +
            (c.tem_senha ? (c.quando_ok ? "sincronizada " + c.quando_ok : "ainda não sincronizada") : "senha não guardada nesta máquina");
        return '<div class="ec-conta' + (c.ultimo_erro ? " problema" : "") + (c.em_uso ? " padrao" : "") + '"><button class="ec-conta-botao" data-ee-abrir="' + esc(c.id) + '">' +
          avatarDaConta(c, true) + '<span class="ec-conta-texto"><b>' + esc(c.email) + "</b><small>" + esc(linha) + "</small></span></button>" +
          '<button class="ec-mais" data-ee-mais="' + esc(c.id) + '" title="Mais" aria-label="Mais">' + ic("more_vert", 18) + "</button></div>";
      }).join("") +
      '<button class="ec-conta-botao ec-outra" data-ee-passo="email"><span class="ec-mais-ic">' + ic("add", 20) + '</span><span class="ec-conta-texto"><b>Usar outra conta</b></span></button></div>' +
      (alguma ? '<div class="ec-pe"><button class="sv-ligacao" id="mail-esquecer">Apagar todas as senhas desta máquina</button></div>' : "");
  } else if (passo === "email") {
    /* O endereco primeiro - e o caminho de quem usa senha de app e o que
       descobre o servidor; os botoes do provedor vem depois do "ou". */
    corpo = "<h2>Entrar em uma conta</h2>" +
      '<label class="ec-campo"><span class="sv-kicker">Endereço de e-mail</span><input type="email" id="ee-email" value="' + esc(e.email) + '" placeholder="nome@dominio.com.br" autocomplete="email"></label>' +
      ecErro(e) +
      '<div class="ec-botoes">' + (contas.length ? '<button data-ee-passo="lista">Voltar</button>' : "") + '<button class="primario" id="ee-avancar">Avançar</button></div>' +
      ecOAuth();
  } else if (passo === "senha") {
    const d = e.deteccao;
    const r = e.prova;
    const c = e.reconectar;
    const linha = (ok, texto, erro) => '<div class="em-conferencia ' + (ok ? "ok" : "aviso") + '">' + ic(ok ? "check_circle" : "error", 18) + "<span>" + texto + (ok ? " funciona" : ": " + esc(erro || "não")) + "</span></div>";
    const servidor = c ? "" : (e.manual
      ? '<div class="ec-manual"><label class="ec-campo"><span class="sv-kicker">IMAP · ler</span><input type="text" id="ee-imap" value="' + esc(e.imap) + '" placeholder="imap.dominio.com.br"></label>' +
        '<label class="ec-campo"><span class="sv-kicker">porta</span><input type="text" id="ee-imap-porta" value="' + esc(e.imapPorta) + '"></label>' +
        '<label class="ec-campo"><span class="sv-kicker">SMTP · enviar</span><input type="text" id="ee-smtp" value="' + esc(e.smtp) + '" placeholder="smtp.dominio.com.br"></label>' +
        '<label class="ec-campo"><span class="sv-kicker">porta</span><input type="text" id="ee-smtp-porta" value="' + esc(e.smtpPorta) + '"></label></div>' +
        (d && !d.achou ? '<p class="ec-nota">' + esc(maiuscula(d.motivo || "não achei o servidor")) + "; preencha à mão. O seu provedor informa esses endereços.</p>" : "")
      : '<div class="ec-servidor">' + ic("lan", 15) + "<span>" + (d ? esc(d.imap_host + " · " + d.smtp_host) : "procurando o servidor…") + "</span>" +
        (d ? '<button class="sv-ligacao" id="ee-manual">mudar</button>' : "") + "</div>");
    let titulo = "Digite a senha";
    let lide = "A mesma senha que você usa no webmail. Se a conta pede senha de app, use essa.";
    if (c && c.ultimo_erro) {
      titulo = "Entrar de novo";
      lide = "O servidor recusou a senha que eu tinha. Digite a atual; eu confiro com o servidor antes de aceitar." +
        (c.guardar_senha ? " Ela substitui a antiga nesta máquina." : "");
    } else if (c) {
      lide = "Esta conta não tem senha guardada nesta máquina. Eu confiro com o servidor antes de abrir a caixa." +
        (c.guardar_senha ? " Se der certo, ela fica guardada." : " Ela vale até você fechar o programa.");
    }
    corpo = ecQuem(e, c ? "lista" : "email") +
      "<h2>" + titulo + "</h2>" +
      '<p class="ec-lide">' + lide + "</p>" +
      (d && d.aviso ? '<div class="ec-aviso"><b>Esta conta não vai funcionar aqui</b><p>' + esc(d.aviso) + "</p></div>" : "") +
      '<label class="ec-campo"><span class="sv-kicker">Senha</span><span class="ec-senha"><input type="' + (e.mostrar ? "text" : "password") + '" id="ee-senha" value="' + esc(e.senha) + '" placeholder="••••••••" autocomplete="current-password">' +
      '<button class="sv-ligacao" id="ee-mostrar">' + (e.mostrar ? "esconder" : "mostrar") + "</button></span></label>" +
      ecErro(e) +
      (r && (!r.entrada || !r.saida) ? '<div class="ec-prova em-conferencias">' + linha(r.entrada, "Ler as mensagens (IMAP)", r.erro_entrada) + linha(r.saida, "Enviar (SMTP)", r.erro_saida) + "</div>" +
        (r.entrada && !r.saida ? '<p class="ec-nota">Dá para ler as mensagens, mas não para enviar por esta conta. <button class="sv-ligacao" id="ee-continuar">Guardar assim mesmo</button></p>' : "") : "") +
      (d && d.ajuda ? '<details class="ec-ajuda"' + (e.ajudaAberta ? " open" : "") + '><summary>Como gerar uma senha de app</summary><p>' + esc(d.ajuda) + "</p></details>" : "") +
      servidor +
      '<div class="ec-botoes"><button class="primario" id="ee-entrar"' + (e.ocupado ? " disabled" : "") + ">" + (e.ocupado ? "Falando com o servidor…" : "Entrar") + "</button></div>";
  } else {
    const pode = mail.contas.pode_guardar_senha;
    corpo = ecQuem(e, "senha") +
      "<h2>" + (pode ? "Manter conectada nesta máquina?" : "Quase pronto") + "</h2>" +
      '<p class="ec-lide">' + (pode ? "Guardo a senha nesta máquina, cifrada pela sua conta do Windows. Assim eu abro a caixa sem perguntar toda vez."
        : "Não consigo guardar senha com segurança neste sistema: vou perguntar quando precisar.") + "</p>" +
      '<label class="ec-campo"><span class="sv-kicker">Seu nome, como aparece para quem recebe</span><input type="text" id="ee-nome" value="' + esc(e.nome) + '" placeholder="Nome e sobrenome"></label>' +
      '<label class="ec-campo"><span class="sv-kicker">Assinatura · opcional</span><textarea id="ee-assinatura" placeholder="Nome · OAB/UF 00000">' + esc(e.assinatura) + "</textarea></label>" +
      '<div class="ag-toggle' + (e.padrao ? " on" : "") + '" data-ee-padrao="1"><span>Usar como conta padrão de envio</span><i></i></div>' +
      ecErro(e) +
      '<div class="ec-botoes">' + (pode ? '<button data-ee-guardar="nao">Não, perguntar sempre</button><button class="primario" data-ee-guardar="sim">Sim, guardar</button>'
        : '<button class="primario" data-ee-guardar="nao">Concluir</button>') + "</div>";
  }
  return '<section class="ec-cartao" data-passo="' + passo + '"><div class="ec-marca"><img src="img/paulus-logo.png" alt=""><span>PAULUS · E-mail</span></div>' + corpo + "</section>";
}

function ecFoco() {
  setTimeout(() => {
    const campo = $("ee-email") || $("ee-senha") || $("ee-nome");
    if (!campo) return;
    campo.focus();
    try { const n = campo.value.length; campo.setSelectionRange(n, n); } catch (err) { /* type=email nao deixa */ }
  }, 0);
}

function ecRedesenhar() { desenharEmail(); ecFoco(); }

async function ecDetectar() {
  const e = ecEstado();
  let d;
  try {
    d = await (await fetch("/api/email/detectar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: e.email }) })).json();
  } catch (err) { d = { achou: false, motivo: String(err) }; }
  e.deteccao = d;
  if (e.reconectar) return;
  if (d.achou) { e.imap = d.imap_host; e.imapPorta = d.imap_porta; e.smtp = d.smtp_host; e.smtpPorta = d.smtp_porta; }
  else e.manual = true;
}

function ecFicha() {
  const e = ecEstado();
  return { email: e.email, nome: e.nome.trim(), imap_host: e.imap.trim(), imap_porta: Number(e.imapPorta) || 993, smtp_host: e.smtp.trim(), smtp_porta: Number(e.smtpPorta) || 587,
    guardar_senha: e.guardar !== false, assinatura: e.assinatura.trim() };
}

async function ecAvancar() {
  const e = ecEstado();
  const v = e.email.trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { e.erro = "Digite o endereço completo, como nome@dominio.com.br."; return ecRedesenhar(); }
  if (mail.contas.contas.some((c) => c.email.toLowerCase() === v.toLowerCase())) { e.erro = "Esta conta já está conectada. Volte e escolha na lista."; return ecRedesenhar(); }
  Object.assign(e, { email: v, erro: "", deteccao: null, manual: false, prova: null, senha: "", passo: "senha" });
  ecRedesenhar();
  await ecDetectar();
  if (ecNaTela() && ecPasso() === "senha") ecRedesenhar();
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
  avisoCert("conta reconectada · " + (conta && conta.tem_senha ? "a senha fica nesta máquina" : "a senha vale até fechar o programa"));
  if (abrir && conta) { mail.conta = conta; return carregarCaixa(); }
  if (ecNaTela()) desenharEmail();
}

async function ecEntrar() {
  const e = ecEstado();
  if (e.ocupado) return;
  if (!e.senha) { e.erro = "Digite a senha."; return ecRedesenhar(); }
  if (e.reconectar) return ecReconectar();
  if (!e.imap.trim() || !e.smtp.trim()) { e.erro = "Preencha os servidores IMAP e SMTP."; e.manual = true; return ecRedesenhar(); }
  e.ocupado = true; e.erro = ""; e.prova = null;
  desenharEmail();
  let r;
  try {
    r = await (await fetch("/api/email/testar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dados: ecFicha(), senha: e.senha }) })).json();
  } catch (err) { r = { ok: false, entrada: false, erro_entrada: String(err) }; }
  e.ocupado = false;
  e.prova = r;
  if (!ecNaTela()) return;
  if (!r.entrada) { e.erro = "Não consegui entrar com essa senha."; return ecRedesenhar(); }
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
  const alvo = e.email.toLowerCase();
  const nova = mail.contas.contas.find((c) => c.email.toLowerCase() === alvo);
  if (e.padrao && nova) {
    const u = await fetch("/api/email/contas/" + nova.id + "/usar", { method: "POST" });
    if (u.ok) mail.contas = await u.json();
  }
  mail.conta = mail.contas.contas.find((c) => c.email.toLowerCase() === alvo) || mail.conta;
  Object.assign(e, ecNovo(), { passo: "lista" });
  avisoCert("conta conectada · " + (sim ? "a senha fica nesta máquina" : "a senha vale até fechar o programa"));
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
      if (p === "lista" || (p === "email" && e.reconectar)) Object.assign(e, ecNovo());
      if (p === "senha") e.prova = null;
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
        if (!(await confirmar({ titulo: "Remover esta conta?", contexto: "E-mail › Contas › " + c.email, texto: "A senha guardada é apagada. As mensagens continuam no seu servidor.", confirmar: "Remover", perigo: true }))) return;
        mail.contas = await (await fetch("/api/email/contas/" + c.id, { method: "DELETE" })).json();
        mail.conta = mail.contas.contas.find((x) => x.em_uso) || mail.contas.contas[0] || null;
        desenharEmail();
      } });
      menuNaLinha(b, itens);
    };
  });
  const esquecer = $("mail-esquecer");
  if (esquecer) esquecer.onclick = async () => {
    if (!(await confirmar({ titulo: "Apagar todas as senhas guardadas?", contexto: "E-mail › Contas", texto: "As contas continuam cadastradas; eu vou perguntar a senha quando precisar.", confirmar: "Apagar senhas", perigo: true }))) return;
    mail.contas = await (await fetch("/api/email/esquecer-senhas", { method: "POST" })).json();
    desenharEmail();
  };
  const guarda = (id, chave) => { const el = $(id); if (el) el.oninput = () => { e[chave] = el.value; }; return el; };
  [["ee-email", "email"], ["ee-senha", "senha"], ["ee-imap", "imap"], ["ee-imap-porta", "imapPorta"], ["ee-smtp", "smtp"], ["ee-smtp-porta", "smtpPorta"], ["ee-nome", "nome"], ["ee-assinatura", "assinatura"]].forEach(([id, k]) => guarda(id, k));
  /* Enter em qualquer campo de uma linha faz o que o botao principal do passo faz. */
  raiz.querySelectorAll(".ec-cartao input").forEach((campo) => {
    campo.onkeydown = (ev) => {
      if (ev.key !== "Enter") return;
      ev.preventDefault();
      const principal = raiz.querySelector(".ec-botoes .primario");
      if (principal && !principal.disabled) principal.click();
    };
  });
  const avancar = $("ee-avancar");
  if (avancar) avancar.onclick = ecAvancar;
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
  if (ecPasso() === "email" && typeof ligarLoginOAuth === "function") {
    const cartao = raiz.querySelector(".ec-cartao");
    if (cartao) ligarLoginOAuth(cartao, ecContaLigada);
  }
  if (ecPasso() === "senha" && e.email && !e.deteccao) ecDetectar().then(() => { if (ecNaTela() && ecPasso() === "senha") desenharEmail(); });
}

(function () {
  const desenharAntes = desenharEmail;
  window.desenharEmail = function () {
    if (mail.visao !== "contas") return desenharAntes();
    cabecalhoEmail();
    $("centro").innerHTML = '<div class="acervo sem-painel ec-tela" id="email"><div class="acervo-principal sv-principal"><div class="ec-palco">' +
      ecCartao() + ecRegras() + "</div></div></div>";
    ligarEmail();
  };
  window.ligarContas = ecLigarContas;
})();
