/* ----------------------------------------------------------- o vinculo */
/*
   O Paulus do servidor vinculado a conta de quem o administra (src/vinculo.py,
   E5) - a conta Google ou, desde 07/10/2026, a conta PAVLVS por e-mail e
   senha. Vinculado, ele abre TRAVADO: esta tela cobre tudo e pede a conta (e
   o codigo do celular, se a conta de titular dessa pessoa tem o
   autenticador). "Manter aberto neste computador" desliga a trava. A trava e
   do servidor: travado, toda outra rota responde 423 - por isso a tela
   recarrega a pagina quando destrava.

   O mesmo login serve ao passo "Sua conta" do assistente de configuracao
   (js/23-boas-vindas.js) e ao cartao em Configuracoes › Escritorio e equipe.
*/

const vinc = { estado: null, relogio: null, aoMudar: null };

async function lerVinculoGoogle() {
  try {
    const r = await fetch("/api/vinculo");
    vinc.estado = r.ok ? await r.json() : null;
  } catch (err) { vinc.estado = null; }
  return vinc.estado;
}

async function postVinculo(url, corpo) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || "não deu certo");
  vinc.estado = d;
  return d;
}

/* Vai ao Google (o navegador abre) e acompanha ate voltar. `aoMudar` e quem
   redesenha (a trava, o passo do assistente, o cartao de Configuracoes). */
async function entrarNoGoogleDoVinculo(finalidade, aoMudar, servicos) {
  vinc.aoMudar = aoMudar;
  await postVinculo("/api/vinculo/entrar", { finalidade, servicos: Boolean(servicos) });
  aoMudar && aoMudar();
  clearInterval(vinc.relogio);
  vinc.relogio = setInterval(async () => {
    const e = await lerVinculoGoogle();
    if (!e || ["pronto", "erro", "cancelado"].includes(e.fase)) clearInterval(vinc.relogio);
    vinc.aoMudar && vinc.aoMudar();
  }, 1000);
}

/* ------------------------------ a conta PAVLVS por e-mail e senha (07/10) */
/*
   O Google deixa de ser obrigatorio: a conta PAVLVS por e-mail e senha
   (src/vinculo.py, worker/identidade.js) faz o mesmo vinculo. O mesmo
   formulario serve ao passo "Sua conta" do assistente (vincular), a trava
   (destravar, com o e-mail fixo) e ao cartao de Configuracoes. Tres modos:
   Entrar; Criar conta (o codigo chega no e-mail e cria a conta); Esqueci a
   senha (outro codigo e a senha nova). Quem decide e paulus.ia.br: aqui so se
   repete a regra da senha e a confirmacao, para avisar antes de enviar.
*/
const contaSenha = { modo: "entrar", etapa: "", email: "", nome: "", senha: "", ocupado: false };

function problemaDaSenha(s) {
  s = String(s || "");
  if (s.length < 10) return "a senha precisa ter pelo menos 10 caracteres";
  if (s.length > 200) return "a senha pode ter no máximo 200 caracteres";
  if (!/[a-zA-ZÀ-ÿ]/.test(s) || !/[0-9]/.test(s)) return "use letras e números na senha";
  return "";
}

function emailParece(e) {
  return /^[^\s@<>"]+@[^\s@<>"]+\.[a-z]{2,}$/i.test(String(e || "").trim());
}

function vincPorSenha() {
  return Boolean(vinc.estado && vinc.estado.vinculado && vinc.estado.por === "senha");
}

/* As rotas /api/vinculo/senha/*: as que entram devolvem o estado do vinculo. */
async function postSenha(url, corpo) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || "não deu certo");
  if (d && "vinculado" in d) vinc.estado = d;
  return d;
}

/* O desenho e o de quem o usa: `o.v` diz as classes (o trilho com a pastilha,
   o rotulo mono, a ajuda, o link e o erro) - o do assistente ou o da trava. */
const VISUAL_BV = { trilho: "bv-g-trilho", pastilha: "bv-g-pastilha", rotulo: "bv-rotulo", ajuda: "bv-ajuda", link: "bv-ligacao", erro: "acesso-erro" };
const VISUAL_TRAVA = { trilho: "trava-trilho", pastilha: "trava-pastilha", rotulo: "trava-etiqueta", ajuda: "trava-ajuda cs-centro", link: "trava-link", erro: "trava-erro" };

function formContaSenha(o) {
  const c = contaSenha;
  const v = o.v || VISUAL_BV;
  if (o.emailFixo) c.email = o.emailFixo;
  const campo = (id, rotulo, tipo, valor, extra) => '<label class="cs-grupo"><span class="' + v.rotulo + '">' + rotulo + "</span>" +
    '<input class="cs-campo" id="cs-' + id + '" type="' + tipo + '" value="' + esc(valor || "") + '"' + (extra || "") + "></label>";
  const email = o.emailFixo ? "" : campo("email", "E-MAIL", "email", c.email, ' autocomplete="username" spellcheck="false" autocapitalize="off"');
  const senha = (id, rotulo, nova) => campo(id, rotulo, "password", "", ' autocomplete="' + (nova ? "new-password" : "current-password") + '"' +
    (nova ? ' placeholder="10 ou mais caracteres, com letras e números"' : "") + ' maxlength="200"');
  const codigo = campo("codigo", "CÓDIGO DO E-MAIL", "text", "", ' inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"');
  const erro = '<p class="' + v.erro + '" id="cs-erro" role="alert"></p>';
  const botao = (texto) => '<button type="submit" class="' + v.trilho + '" id="cs-enviar"' + (c.ocupado ? " disabled" : "") + '><span class="' + v.pastilha + '">' +
    esc(texto) + "</span></button>";
  const link = (acao, texto) => '<button type="button" class="' + v.link + '" data-cs="' + acao + '">' + texto + "</button>";
  const para = "<b>" + esc(c.email) + "</b>";
  let miolo;
  let links;
  if (c.modo === "criar" && c.etapa === "codigo") {
    miolo = '<p class="' + v.ajuda + '">Enviamos um código de 6 números para ' + para + ". Ele vale 15 minutos.</p>" + codigo + erro + botao("Confirmar e entrar");
    links = link("reenviar", "Reenviar código") + link("voltar", "Voltar");
  } else if (c.modo === "criar") {
    miolo = campo("nome", "NOME", "text", c.nome, ' autocomplete="name" maxlength="80"') + email + senha("senha", "SENHA", true) +
      senha("repetir", "CONFIRMAR A SENHA", true) + erro + botao("Criar conta");
    links = link("entrar", "Já tenho conta");
  } else if (c.modo === "esqueci" && c.etapa === "codigo") {
    miolo = '<p class="' + v.ajuda + '">Se ' + para + " tem conta PAVLVS (ou já entrou com o Google), enviamos um código de 6 números. Ele vale 15 minutos.</p>" +
      codigo + senha("senha", "NOVA SENHA", true) + senha("repetir", "CONFIRMAR A NOVA SENHA", true) + erro + botao("Trocar a senha e entrar");
    links = link("reenviar", "Reenviar código") + link("voltar", "Voltar");
  } else if (c.modo === "esqueci") {
    miolo = (o.emailFixo ? '<p class="' + v.ajuda + '">O código para trocar a senha vai para ' + para + ".</p>" : email) + erro + botao("Enviar código");
    links = link("entrar", "Voltar");
  } else {
    miolo = email + senha("senha", "SENHA", false) + erro + botao("Entrar");
    links = link("esqueci", "Esqueci a senha") + link("criar", "Criar conta");
  }
  return '<form class="cs-form" id="cs-form" novalidate>' + miolo + '<div class="cs-links">' + links + "</div></form>";
}

/* `o.finalidade`: vincular ou destravar; `o.aoEntrar(estado)` segue depois de
   entrar; `o.redesenhar()` refaz a tela quando o modo muda. */
function ligarContaSenha(raiz, o) {
  const form = raiz.querySelector("#cs-form");
  if (!form) return;
  const c = contaSenha;
  const valor = (id) => { const el = form.querySelector("#cs-" + id); return el ? el.value : ""; };
  const erro = (msg) => { const p = form.querySelector("#cs-erro"); if (p) p.textContent = msg ? maiuscula(msg) : ""; };
  const ir = (modo, etapa) => { c.modo = modo; c.etapa = etapa || ""; c.ocupado = false; o.redesenhar(); };
  form.querySelectorAll("input").forEach((i) => {
    i.oninput = () => { if (i.id === "cs-email") c.email = i.value.trim(); if (i.id === "cs-nome") c.nome = i.value; };
  });
  form.querySelectorAll("[data-cs]").forEach((b) => {
    b.onclick = async (ev) => {
      ev.preventDefault();
      const acao = b.dataset.cs;
      if (acao === "reenviar") {
        try {
          if (c.modo === "criar") await postSenha("/api/vinculo/senha/cadastrar", { email: c.email, senha: c.senha, nome: c.nome });
          else await postSenha("/api/vinculo/senha/esqueci", { email: c.email });
          avisoCert("código enviado de novo para " + c.email);
        } catch (err) { erro(err.message); }
        return;
      }
      if (acao === "voltar") { c.senha = ""; ir(c.modo, ""); return; }
      c.senha = "";
      ir(acao === "entrar" ? "entrar" : acao, "");
    };
  });
  const entrou = async (d) => {
    c.modo = "entrar"; c.etapa = ""; c.senha = ""; c.ocupado = false;
    if (o.aoEntrar) await o.aoEntrar(d);
  };
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    erro("");
    // Na trava o e-mail e fixo (o da conta deste servidor): sem campo, vale o guardado.
    if (form.querySelector("#cs-email")) c.email = valor("email").trim();
    let falta = "";
    let url = "";
    let corpo = {};
    if (!emailParece(c.email)) falta = "confira o e-mail";
    else if (c.modo === "criar" && c.etapa === "codigo") {
      if (!/^\d{6}$/.test(valor("codigo").replace(/\D/g, ""))) falta = "o código tem 6 números";
      url = "/api/vinculo/senha/confirmar"; corpo = { email: c.email, codigo: valor("codigo").replace(/\D/g, ""), finalidade: o.finalidade };
    } else if (c.modo === "criar") {
      c.nome = valor("nome");
      falta = problemaDaSenha(valor("senha")) || (valor("senha") !== valor("repetir") ? "as duas senhas não são iguais" : "");
      url = "/api/vinculo/senha/cadastrar"; corpo = { email: c.email, senha: valor("senha"), nome: c.nome.trim() };
    } else if (c.modo === "esqueci" && c.etapa === "codigo") {
      if (!/^\d{6}$/.test(valor("codigo").replace(/\D/g, ""))) falta = "o código tem 6 números";
      else falta = problemaDaSenha(valor("senha")) || (valor("senha") !== valor("repetir") ? "as duas senhas não são iguais" : "");
      url = "/api/vinculo/senha/redefinir";
      corpo = { email: c.email, codigo: valor("codigo").replace(/\D/g, ""), senha: valor("senha"), finalidade: o.finalidade };
    } else if (c.modo === "esqueci") {
      url = "/api/vinculo/senha/esqueci"; corpo = { email: c.email };
    } else {
      if (!valor("senha")) falta = "digite a senha";
      url = "/api/vinculo/senha/entrar"; corpo = { email: c.email, senha: valor("senha"), finalidade: o.finalidade };
    }
    if (falta) { erro(falta); return; }
    const b = form.querySelector("#cs-enviar");
    if (b) b.disabled = true;
    c.ocupado = true;
    try {
      const d = await postSenha(url, corpo);
      c.ocupado = false;
      if (c.modo === "criar" && !c.etapa) { c.senha = corpo.senha; ir("criar", "codigo"); return; }
      if (c.modo === "esqueci" && !c.etapa) { ir("esqueci", "codigo"); return; }
      await entrou(d);
    } catch (err) {
      c.ocupado = false;
      if (b) b.disabled = false;
      erro(err.message);
    }
  };
  // O foco no primeiro campo vazio: quem chega ao passo do codigo ja digita.
  const vazio = Array.from(form.querySelectorAll("input")).find((i) => !i.value);
  if (vazio && o.focar !== false) vazio.focus();
}

/* Confirmar a conta vinculada pela senha (um token novo, 1 h): o acesso de
   fora e a nuvem pedem, para paulus.ia.br saber de quem e. Pelo Google, quem
   chama abre o navegador como sempre. true quando confirmou. */
async function confirmarComSenha() {
  const e = vinc.estado || (await lerVinculoGoogle()) || {};
  const r = await dialogo({ titulo: "Confirme a sua conta", contexto: e.email || "",
    texto: "Digite a senha da sua conta PAVLVS. Ela vai só a paulus.ia.br, para confirmar que é você.",
    campo: { rotulo: "Senha", tipo: "password", selecionar: false }, confirmar: "Confirmar" });
  if (!r || !r.ok) return false;
  try {
    await postSenha("/api/vinculo/senha/entrar", { finalidade: "confirmar", email: e.email, senha: r.valor });
    return true;
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return false; }
}

/* ------------------------------------------------------------ a trava */

const G_DO_GOOGLE = '<svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';

function telaDaTrava() {
  let el = document.getElementById("trava");
  if (!el) {
    el = document.createElement("div");
    el.id = "trava";
    el.className = "trava";
    document.body.appendChild(el);
  }
  return el;
}

function desenharTrava() {
  const e = vinc.estado || {};
  if (!e.travado) {
    const el = document.getElementById("trava");
    if (el) {
      el.remove();
      // Destravou: a pagina volta a ler tudo o que o servidor recusava.
      location.reload();
    }
    return;
  }
  // O desenho "Servidor - Entrar" (02/10/2026): a coluna de 360 px no meio,
  // como a tela de entrar de fora (frontend/entrar.html) - a conta deste
  // servidor, manter aberto, o Google no trilho, a senha da conta PAVLVS
  // (07/10) e, embaixo, o que continua funcionando enquanto a janela esta
  // travada. O codigo e a chave seguem o mesmo desenho ("Codigo" e "Chave de
  // recuperacao").
  const esperando = e.fase === "aguardando" || e.fase === "trocando" || e.fase === "testando";
  const fora = e.acesso_de_fora || {};
  const foraNoAr = Boolean(fora.ligado && fora.hostname);
  const recuperacao = Boolean(vinc.porRecuperacao);
  const semNet = Boolean(vinc.semInternet) && !e.precisa_codigo;
  const codigo = e.precisa_codigo || semNet;
  const pronto = Boolean((e.sem_internet || {}).pronto);
  const conta = (rotulo, trocar) => '<div class="trava-grupo"><span class="trava-etiqueta">' + rotulo + "</span>" +
    '<div class="trava-caixa">' + (semNet ? ic("desktop_windows", 16) : e.por === "senha" ? ic("mail", 16) : G_DO_GOOGLE) + '<span class="trava-email">' + esc(e.email) + "</span>" +
    (trocar ? '<button type="button" class="trava-trocar" id="trava-trocar">' + esc(trocar) + "</button>" : "") + "</div></div>";
  const trilho = (id, texto, google, desligado) => '<button type="' + (google ? "button" : "submit") + '" class="trava-trilho" id="' + id + '"' +
    (desligado ? " disabled" : "") + '><span class="trava-pastilha">' + (google ? G_DO_GOOGLE : "") + esc(texto) + "</span></button>";
  let frase, corpo, tela;
  if (codigo) {
    tela = recuperacao ? "chave" : semNet ? "trava_sem_internet" : "trava_codigo";
    frase = recuperacao ? "Use uma das chaves de recuperação que você guardou. Cada uma vale uma vez." : semNet
      ? "Sem internet, o código do celular abre o Paulus neste computador." : "Falta confirmar que é você: digite o código do Google Authenticator.";
    const n = recuperacao ? 0 : 6;
    corpo = '<form class="trava-form" id="trava-codigo">' +
      conta("CONTA", recuperacao ? "" : (semNet ? "Entrar com a conta" : "Trocar")) +
      '<div class="trava-grupo"><div class="trava-rotulo-linha"><span class="trava-etiqueta">' + (recuperacao ? "CHAVE DE RECUPERAÇÃO" : "GOOGLE AUTHENTICATOR") +
      '</span><span class="trava-renova" id="trava-renova">' + (recuperacao ? "uso único" : "renova em <b>00:30</b>") + "</span></div>" +
      '<div class="trava-casas' + (recuperacao ? " campo" : "") + '" id="trava-casas" style="--n:' + (n || 6) + '">' +
      '<input id="trava-codigo-campo"' + (recuperacao ? ' autocomplete="off" maxlength="9" aria-label="Chave de recuperação"'
        : ' inputmode="numeric" autocomplete="one-time-code" maxlength="6" aria-label="Código de 6 dígitos"') + "></div>" +
      (recuperacao ? '<span class="trava-ajuda">Cada chave vale uma vez.</span>' : "") + "</div>" +
      // "Nao pedir o codigo neste computador por 30 dias": so depois da conta
      // (Google ou senha; o mesmo do "Confiar neste navegador" de quem entra de fora).
      (!recuperacao && !semNet ? '<label class="trava-manter"><input type="checkbox" id="trava-confiar"' + (vinc.confiarCodigo ? " checked" : "") +
        '><i aria-hidden="true">' + ic("check", 13) + "</i><span>Não pedir o código neste computador por 30 dias</span></label>" : "") +
      '<p class="trava-erro" id="trava-erro"></p>' +
      trilho("trava-abrir", "Abrir o PAVLVS", false, false) +
      '<button type="button" class="trava-link" id="trava-recuperacao">' + (recuperacao ? "Usar o Google Authenticator" : "Não tenho o celular") + "</button></form>";
  } else {
    tela = "trava";
    frase = "Entre com a sua conta para abrir o escritório.";
    // O Google (quando esta versao o traz) e a senha da conta PAVLVS, com o
    // e-mail fixo: so a conta deste servidor abre. Criar conta e Esqueci a
    // senha trocam o formulario e escondem o Google ate voltar.
    const noComeco = contaSenha.modo === "entrar" && !contaSenha.etapa;
    corpo = '<div class="trava-form">' + conta("CONTA DESTE SERVIDOR", "") +
      '<label class="trava-manter"><input type="checkbox" id="trava-manter"' + (vinc.manterAoEntrar ? " checked" : "") + '><i aria-hidden="true">' +
      ic("check", 13) + "</i><span>Manter aberto neste computador</span></label>" +
      (noComeco && e.google ? trilho("trava-google", esperando ? "Esperando o Google…" : "Entrar com Google", true, esperando) +
        (esperando ? '<button type="button" class="trava-link" id="trava-cancelar">Cancelar</button>' : "") +
        '<p class="trava-erro" id="trava-erro">' + esc(e.fase === "erro" ? e.mensagem : "") + "</p>" +
        '<div class="cs-ou">OU COM A SENHA</div>' : "") +
      formContaSenha({ emailFixo: e.email, v: VISUAL_TRAVA }) +
      '<div class="trava-grupo trava-enquanto"><span class="trava-etiqueta">ENQUANTO ISSO</span>' +
      // A Cloudflare a esquerda; o estado em duas linhas (frase e, embaixo, o endereco); a bolinha a direita.
      '<div class="trava-fora"><span class="trava-fora-marca">' + window.marca("cloudflare", 20) + "</span>" +
      '<span class="trava-estado-txt"><b>' + (foraNoAr ? "Acesso externo funcionando corretamente" : "Acesso externo desligado") + "</b>" +
      (foraNoAr ? '<a class="trava-mono" href="' + esc("https://" + fora.hostname) + '" target="_blank" rel="noopener">' + esc(fora.hostname) + "</a>" : "") + "</span>" +
      '<span class="trava-estado' + (foraNoAr ? " ok" : "") + '" aria-label="' + (foraNoAr ? "no ar" : "desligado") + '"><i></i></span></div></div>' +
      (pronto ? '<button type="button" class="trava-link" id="trava-sem-internet">Sem internet? Entre com o código do celular</button>' : "") +
      "</div>";
  }
  const escuro = document.documentElement.dataset.tema === "escuro";
  // O alto ("Paulus está te esperando." e a frase) sobrevive ao redesenho:
  // a tela e refeita a cada mudanca de estado, e a saudacao so troca quando
  // muda o passo (js/entrada-saudacao.js).
  const antes = telaDaTrava().querySelector(".trava-marca");
  telaDaTrava().innerHTML =
    '<header class="trava-topo pywebview-drag-region"><span class="trava-marca-nome">PAVLVS</span>' +
    '<button type="button" class="trava-tema" id="trava-tema" aria-label="Alternar tema">' + ic(escuro ? "light_mode" : "dark_mode", 16) + "</button></header>" +
    '<main class="trava-corpo">' + (codigo ? '<button type="button" class="trava-voltar" id="trava-voltar">' + ic("arrow_back", 18) + "Voltar</button>" : "") +
    '<div class="trava-coluna"><div class="trava-marca abrindo"><h1 data-es-titulo>Paulus está te esperando.</h1><p data-es-frase>' + esc(frase) +
    "</p></div>" + corpo + "</div></main>";
  const marca = telaDaTrava().querySelector(".trava-marca");
  if (antes) marca.replaceWith(antes);
  saudarNaTrava(antes || marca, tela);
  ligarTrava();
}

function saudarNaTrava(bloco, tela) {
  if (typeof EntradaSaudacao === "undefined") { bloco.classList.remove("abrindo"); return; }
  if (!bloco.dataset.aberto) { bloco.dataset.aberto = "1"; EntradaSaudacao.abrir(bloco, tela); }
  else EntradaSaudacao.trocar(bloco, tela);
}

function ligarTrava() {
  const t = document.getElementById("trava-tema");
  if (t) t.onclick = () => { alternarTema(); desenharTrava(); };
  const m = document.getElementById("trava-manter");
  if (m) m.onchange = () => { vinc.manterAoEntrar = m.checked; };
  const cf = document.getElementById("trava-confiar");
  if (cf) cf.onchange = () => { vinc.confiarCodigo = cf.checked; };
  const b = document.getElementById("trava-google");
  if (b) b.onclick = async () => {
    const manter = document.getElementById("trava-manter");
    vinc.manterAoEntrar = Boolean(manter && manter.checked);
    try { await entrarNoGoogleDoVinculo("destravar", aoMudarNaTrava); }
    catch (err) { const p = document.getElementById("trava-erro"); if (p) p.textContent = err.message; }
  };
  const tr = document.getElementById("trava-trocar");
  if (tr) tr.onclick = async () => {
    vinc.porRecuperacao = false;
    if (vinc.semInternet) { vinc.semInternet = false; desenharTrava(); return; }
    await postVinculo("/api/vinculo/cancelar").catch(() => {});
    desenharTrava();
  };
  ligarContaSenha(telaDaTrava(), {
    finalidade: "destravar", focar: false, redesenhar: desenharTrava,
    aoEntrar: async () => {
      const manter = document.getElementById("trava-manter");
      vinc.manterAoEntrar = Boolean(manter && manter.checked);
      await aoMudarNaTrava();
    },
  });
  const sn = document.getElementById("trava-sem-internet");
  if (sn) sn.onclick = () => { vinc.semInternet = true; vinc.porRecuperacao = false; desenharTrava(); };
  const rec = document.getElementById("trava-recuperacao");
  if (rec) rec.onclick = () => { vinc.porRecuperacao = !vinc.porRecuperacao; desenharTrava(); };
  const c = document.getElementById("trava-cancelar");
  if (c) c.onclick = async () => { await postVinculo("/api/vinculo/cancelar").catch(() => {}); desenharTrava(); };
  const v = document.getElementById("trava-voltar");
  if (v) v.onclick = async () => {
    vinc.porRecuperacao = false;
    if (vinc.semInternet) { vinc.semInternet = false; desenharTrava(); return; }
    await postVinculo("/api/vinculo/cancelar").catch(() => {});
    desenharTrava();
  };
  const f = document.getElementById("trava-codigo");
  if (f) {
    const campo = document.getElementById("trava-codigo-campo");
    // As seis casas: o campo de verdade fica por cima, transparente.
    const casas = document.getElementById("trava-casas");
    const desenhar = () => {
      if (casas.classList.contains("campo")) return;
      const val = campo.value.replace(/\D/g, "").slice(0, 6);
      casas.querySelectorAll("span").forEach((x) => x.remove());
      for (let i = 0; i < 6; i++) {
        const x = document.createElement("span");
        x.textContent = val[i] || "";
        if (i === Math.min(val.length, 5) && document.activeElement === campo) x.classList.add("vez");
        casas.insertBefore(x, campo);
      }
    };
    campo.addEventListener("input", desenhar);
    campo.addEventListener("focus", desenhar);
    campo.addEventListener("blur", desenhar);
    const renova = () => {
      const b = document.querySelector("#trava-renova b");
      if (!b) { clearInterval(vinc.renova); return; }
      b.textContent = "00:" + String(30 - (Math.floor(Date.now() / 1000) % 30)).padStart(2, "0");
    };
    clearInterval(vinc.renova);
    renova();
    vinc.renova = setInterval(renova, 1000);
    campo.focus();
    desenhar();
    f.onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        const semNet = vinc.semInternet && !(vinc.estado || {}).precisa_codigo;
        const confiar = document.getElementById("trava-confiar");
        await postVinculo(semNet ? "/api/vinculo/sem-internet" : "/api/vinculo/codigo",
          semNet ? { codigo: campo.value.trim() } : { codigo: campo.value.trim(), confiar: Boolean(confiar && confiar.checked) });
        vinc.semInternet = false;
        await aoDestravar();
      } catch (err) { document.getElementById("trava-erro").textContent = err.message; campo.select(); }
    };
  }
}

async function aoMudarNaTrava() {
  const e = vinc.estado || {};
  if (!e.travado) { await aoDestravar(); return; }
  desenharTrava();
}

async function aoDestravar() {
  // "Manter aberto" marcado na trava: vale a partir de agora.
  if (vinc.manterAoEntrar) { await postVinculo("/api/vinculo/manter-aberto", { ligado: true }).catch(() => {}); }
  desenharTrava();
}

/* O servidor recusou por estar travado (423): a trava aparece, venha de onde vier. */
async function mostrarTrava() {
  await lerVinculoGoogle();
  if (vinc.estado && vinc.estado.travado && !document.getElementById("trava")) desenharTrava();
}

acessoDeFora.pronto.then(async () => {
  if (!acessoDeFora.local) return;
  const e = await lerVinculoGoogle();
  mostrarBotaoSair();
  if (e && e.travado) desenharTrava();
});

/* ------------------------------------------------ sair (no servidor) */
/*
   "Sair", na barra da janela do servidor: trava o Paulus na hora - mesmo com
   "manter aberto" - para ninguem mexer no computador do escritorio. Quem
   entra de fora nao passa pela trava: com o programa aberto, a equipe
   continua entrando pelo endereco. De fora, o "Sair" e o da propria conta
   (js/00-acesso.js).
*/
function mostrarBotaoSair() {
  const ver = Boolean(acessoDeFora.local);
  ["sair-servidor", "sair-servidor-menu"].forEach((id) => {
    const b = document.getElementById(id);
    if (!b) return;
    b.hidden = !ver;
    b.onclick = (ev) => { ev.stopPropagation(); sairDoServidor(); };
  });
}

async function sairDoServidor() {
  const e = (await lerVinculoGoogle()) || {};
  if (!e.vinculado) {
    const ir = await confirmar({ titulo: "Sair da conta", contexto: "servidor do escritório",
      texto: "Para sair, este Paulus precisa estar vinculado a uma conta (Google ou e-mail e senha): é com ela que se entra de novo. Vincule em Configurações › Escritório e equipe.",
      confirmar: "Vincular agora" });
    if (ir) mostrarConfig("vinculos");
    return;
  }
  try {
    await postVinculo("/api/vinculo/travar");
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return; }
  desenharTrava();
}

/* ----------------------------------------- o cartao de Configuracoes */

function cartaoDoVinculo() {
  const e = vinc.estado;
  if (!e) return "";
  const esperando = e.fase === "aguardando" || e.fase === "trocando" || e.fase === "testando";
  if (!e.vinculado) {
    // Pelo Google ou pela conta PAVLVS de e-mail e senha (o formulario abre no proprio cartao).
    return cartaoCfg("Conta deste Paulus", metaCfg("não vinculado"),
      '<p class="cfg-texto">Vincule este Paulus à sua conta — a do Google ou uma conta PAVLVS com e-mail e senha: ele passa a abrir travado e pede a conta a cada abertura (dá para manter aberto neste computador). O vínculo é exigido para ligar o acesso externo e convidar a equipe.</p>' +
      (e.fase === "erro" ? '<p class="acesso-erro">' + esc(e.mensagem) + "</p>" : "") +
      '<div class="acesso-pe">' + (e.google ? '<button class="primario com-icone" data-vinc-vincular="1"' + (esperando ? " disabled" : "") + ">" +
      (esperando ? "Esperando o Google no navegador…" : "Vincular com Google") + "</button>" : "") +
      (esperando ? '<button data-vinc-cancelar="1">Cancelar</button>' : "") +
      '<button class="com-icone" data-vinc-senha="1">' + ic("mail", 16) + (vinc.cfgSenha ? "Fechar o e-mail e senha" : "Vincular com e-mail e senha") + "</button></div>" +
      (vinc.cfgSenha ? '<div class="bv-entrada cs-no-cartao">' + formContaSenha({ v: VISUAL_BV }) + "</div>" : ""));
  }
  const quando = e.vinculado_em ? new Date(e.vinculado_em).toLocaleDateString("pt-BR") : "";
  return cartaoCfg("Conta deste Paulus", pontoCfg("vinculado", "ok"),
    '<div class="cfg-linhas">' + chaveCfg("Conta", e.email) + chaveCfg("Entra com", e.por === "senha" ? "e-mail e senha (conta PAVLVS)" : "Google") +
    (e.nome ? chaveCfg("Nome", e.nome) : "") + (quando ? chaveCfg("Desde", quando) : "") + "</div>" +
    '<div class="acesso-energia">' +
    ligaCfg("", "Manter aberto neste computador", e.manter_aberto
      ? "o Paulus abre sem pedir a conta neste computador"
      : "o Paulus abre travado e pede a conta a cada abertura", e.manter_aberto, false)
      .replace('class="ag-toggle', 'data-vinc-manter="1" class="ag-toggle') + "</div>" +
    (e.codigo_confiado_ate
      ? '<div class="cfg-linhas">' + chaveCfg("Código do celular", "dispensado neste computador até " +
          new Date(e.codigo_confiado_ate).toLocaleDateString("pt-BR")) + "</div>" +
        '<div class="cfg-botoes"><button data-vinc-esquecer-codigo="1">Pedir o código de novo</button></div>'
      : "") +
    blocoSemInternet(e) +
    '<div class="acesso-pe"><button class="com-icone" data-vinc-travar="1">' + ic("logout", 16) + "Sair</button>" +
    '<button class="perigo" data-vinc-desvincular="1">Desvincular</button>' +
    '<p class="cfg-explica">Sair trava este computador até alguém entrar com a conta vinculada (o acesso externo continua). Desvincular não apaga nada: o Paulus só deixa de pedir a conta ao abrir.</p></div>');
}

/* Entrar sem internet (src/vinculo.py): o login do servidor nao depende do
   Google. Com a conta de titular do mesmo e-mail, o codigo dela ja vale; sem
   ela, o servidor ganha um codigo proprio, ligado aqui com o QR. */
function blocoSemInternet(e) {
  const si = e.sem_internet || {};
  const miolo = vinc.semNetNovo
    ? '<div class="acesso-qr-bloco"><div class="acesso-qr">' + (vinc.semNetNovo.qr_svg || "") + "</div>" +
      '<div class="acesso-qr-texto"><p>No celular, abra o <b>Google Authenticator</b>, toque em <b>+</b> e em <b>Ler código QR</b>.</p>' +
      '<p class="cfg-explica">Sem câmera? Digite a chave:</p><code class="acesso-segredo">' +
      esc((vinc.semNetNovo.segredo || "").replace(/(.{4})/g, "$1 ").trim()) + "</code></div></div>" +
      '<div class="acesso-form"><div class="ag-campo"><label for="vinc-sn-codigo">Código de 6 números que aparece no aplicativo</label>' +
      '<input type="text" id="vinc-sn-codigo" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"></div></div>' +
      '<div class="acesso-pe"><button class="primario" data-vinc-sn-confirmar="1">Confirmar o código</button>' +
      '<button data-vinc-sn-cancelar="1">Cancelar</button></div>'
    : vinc.semNetCodigos
      ? '<p class="cfg-texto">Guarde estes códigos fora do celular: cada um abre o PAVLVS uma vez, sem internet, se o celular sumir. Eles não aparecem de novo.</p>' +
        '<div class="acesso-codigos">' + vinc.semNetCodigos.map((x) => "<code>" + esc(x) + "</code>").join("") + "</div>" +
        '<div class="acesso-pe"><button class="primario" data-vinc-sn-guardei="1">Guardei os códigos</button></div>'
      : si.por === "titular"
        ? '<p class="cfg-explica">' + ic("check_circle", 14) + " Pronto: sem internet, o código do celular da sua conta de titular abre este PAVLVS.</p>"
        : si.por === "servidor"
          ? '<p class="cfg-explica">' + ic("check_circle", 14) + " Pronto: sem internet, o código do celular deste servidor abre o PAVLVS" +
            (si.recuperacao_restantes != null ? " · " + si.recuperacao_restantes + " códigos de recuperação" : "") + ".</p>" +
            '<div class="cfg-botoes"><button data-vinc-sn-desligar="1">Desligar</button></div>'
          : '<p class="cfg-explica">Sem internet, nem o Google nem paulus.ia.br respondem, e o PAVLVS travado não abre. Ligue o código do celular: o Google Authenticator funciona sem conexão.</p>' +
            '<div class="cfg-botoes"><button class="com-icone" data-vinc-sn-ligar="1">' + ic("shield_person", 16) + "Ligar entrar sem internet</button></div>";
  return '<div class="acesso-energia"><b>Entrar sem internet</b>' + miolo + "</div>";
}

function ligarVinculoCfg() {
  const redesenhar = () => { if (typeof desenharConfig === "function") desenharConfig(); };
  const clique = (sel, fn) => document.querySelectorAll(sel).forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fn(b); }; });
  clique("[data-vinc-vincular]", async () => {
    try { await entrarNoGoogleDoVinculo("vincular", redesenhar); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  });
  clique("[data-vinc-cancelar]", async () => { await postVinculo("/api/vinculo/cancelar").catch(() => {}); redesenhar(); });
  clique("[data-vinc-senha]", () => { vinc.cfgSenha = !vinc.cfgSenha; redesenhar(); });
  ligarContaSenha(document, {
    finalidade: "vincular", redesenhar, focar: false,
    aoEntrar: async () => { vinc.cfgSenha = false; avisoCert("vinculado: " + ((vinc.estado || {}).email || ""), { tom: "ok" }); redesenhar(); },
  });
  clique("[data-vinc-manter]", async (b) => {
    try { await postVinculo("/api/vinculo/manter-aberto", { ligado: !b.classList.contains("on") }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-travar]", () => sairDoServidor());
  clique("[data-vinc-esquecer-codigo]", async () => {
    try {
      vinc.estado = await postVinculo("/api/vinculo/esquecer-codigo", {});
      avisoCert("O código do celular volta a ser pedido neste computador.");
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    if (typeof desenharConfig === "function") desenharConfig();
  });
  clique("[data-vinc-sn-ligar]", async () => {
    try {
      const r = await fetch("/api/vinculo/sem-internet/ligar", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "não deu certo");
      vinc.semNetNovo = d;
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-sn-cancelar]", () => { vinc.semNetNovo = null; redesenhar(); });
  clique("[data-vinc-sn-confirmar]", async () => {
    const campo = document.getElementById("vinc-sn-codigo");
    try {
      const r = await fetch("/api/vinculo/sem-internet/confirmar", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ codigo: campo ? campo.value.trim() : "" }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "não deu certo");
      vinc.semNetNovo = null;
      vinc.semNetCodigos = d.codigos_recuperacao || [];
      vinc.estado = d.estado || vinc.estado;
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-sn-guardei]", () => { vinc.semNetCodigos = null; redesenhar(); });
  clique("[data-vinc-sn-desligar]", async () => {
    try { await postVinculo("/api/vinculo/sem-internet/desligar"); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
  clique("[data-vinc-desvincular]", async () => {
    if (!(await confirmar({ titulo: "Desvincular a conta?", contexto: "Configurações › Escritório e equipe",
      texto: "O Paulus deixa de pedir a conta ao abrir. Para ligar o acesso externo e convidar a equipe, vai ser preciso vincular de novo.",
      confirmar: "Desvincular", perigo: true }))) return;
    try { await postVinculo("/api/vinculo/desvincular"); avisoCert("desvinculado", { tom: "ok" }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    redesenhar();
  });
}
