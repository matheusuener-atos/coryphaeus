/* ------------------------------------------------------ acesso de fora */
/*
   Configuracoes › Acesso de fora (acesso-remoto/v0). So existe na janela do
   programa: de fora, Configuracoes nao abre, e as rotas daqui recusam mesmo
   com sessao valida - uma sessao roubada nao cria conta nem religa nada.

   R2: as contas. Cada pessoa que vai entrar de fora tem uma conta propria -
   nome, e-mail, senha e o aplicativo autenticador do celular. A primeira e
   sempre do titular.
*/

const acessoCfg = { contas: null, sessoes: [], disponivel: true };

async function carregarAcesso() {
  try {
    const r = await fetch("/api/acesso/contas");
    const d = r.ok ? await r.json() : null;
    acessoCfg.contas = d ? d.contas : null;
    acessoCfg.sessoes = (d && d.sessoes) || [];
    acessoCfg.disponivel = !d || d.disponivel !== false;
  } catch (err) {
    acessoCfg.contas = null;
  }
  if (typeof carregarTunel === "function") await carregarTunel();
}

function secaoAcesso() {
  const contas = acessoCfg.contas || [];
  const prontas = contas.filter((c) => c.totp_confirmado).length;
  const ligado = Boolean(((cfg.prefs || {}).preferencias || {}).acesso_remoto && cfg.prefs.preferencias.acesso_remoto.ligado);
  const ficha = fichaCfg([
    ["Acesso de fora", ligado ? "ligado" : "desligado", ligado ? "ok" : ""],
    ["Contas prontas", prontas + " de " + contas.length],
    ["Sessões abertas", String(acessoCfg.sessoes.length)],
  ]);
  const tunel = typeof cartaoTunel === "function" ? cartaoTunel() : "";
  return aberturaCfg() + ficha + cartaoComoFunciona() + tunel + cartaoContas() + cartaoSessoes();
}

/* O que a pessoa precisa saber antes de ligar, dito sem enfeite. E a mesma
   lista do assistente de conexao e da politica de privacidade. */
function cartaoComoFunciona() {
  const itens = [
    ["desktop_windows", "O computador do escritório precisa estar ligado e com o PAULUS aberto. Desligado, o endereço para de responder."],
    ["key", "Os documentos, o índice e o modelo de IA não saem deste computador. O que passa pela internet é a tela e o que se digita nela."],
    ["lan", "O caminho é o túnel da Cloudflare, num endereço paulus.ia.br da conta do Atos. A conexão é criptografada, mas a Cloudflare a abre no meio do caminho para entregá-la; o Atos não roteia, não inspeciona e não registra esse conteúdo."],
    ["verified", "Para entrar: o e-mail confirmado pela Cloudflare, depois a conta do PAULUS com senha e o código do autenticador do celular."],
    ["history", "Todo acesso de fora fica registrado neste computador: quem entrou, quando, o que abriu e o que baixou."],
  ];
  return cartaoCfg("Como funciona", "",
    '<div class="acesso-itens">' + itens.map(([icone, texto]) =>
      '<div class="acesso-item"><span class="caixa-tipo">' + ic(icone, 18) + "</span><p>" + esc(texto) + "</p></div>").join("") + "</div>");
}

function cartaoContas() {
  if (acessoCfg.contas === null) return cartaoCfg("Contas", "", '<p class="cfg-texto">não consegui ler as contas.</p>');
  if (!acessoCfg.disponivel) {
    return cartaoCfg("Contas", metaCfg("indisponível"),
      '<p class="cfg-texto">Este computador não tem como guardar o segredo do autenticador com proteção (a proteção de dados do Windows). Sem isso, o acesso de fora fica desligado.</p>');
  }
  const contas = acessoCfg.contas;
  const linhas = contas.map((c) => {
    const estado = c.totp_confirmado
      ? '<span class="fin-meta-ponto ok"><i></i>pronta</span>'
      : '<span class="fin-meta-ponto acc"><i></i>falta o autenticador</span>';
    const sub = c.email + " · " + (c.papel === "titular" ? "titular" : "colaborador") +
      (c.totp_confirmado ? " · " + plural(c.codigos_restantes, "código", "códigos") + " de recuperação" : "");
    return '<div class="cfg-servico"><span class="caixa-tipo">' + ic(c.papel === "titular" ? "shield_person" : "person", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" + esc(sub) + "</small></span>" + estado +
      '<span class="cfg-botoes">' +
      (c.totp_confirmado ? "" : '<button data-acesso-confirmar="' + c.id + '">Confirmar</button>') +
      '<button data-acesso-senha="' + c.id + '">Senha</button>' +
      '<button data-acesso-autenticador="' + c.id + '">Autenticador</button>' +
      '<button data-acesso-codigos="' + c.id + '">Códigos</button>' +
      '<button class="mais-linha" data-acesso-remover="' + c.id + '" title="Remover a conta" aria-label="Remover a conta">' + ic("close", 16) + "</button>" +
      "</span></div>";
  }).join("");
  const vazio = '<p class="cfg-texto">Nenhuma conta ainda. A primeira é a do titular: quem cuida das contas e pode aprovar de fora.</p>';
  return cartaoCfg("Contas", metaCfg(contas.length ? plural(contas.length, "conta") : "nenhuma"),
    (contas.length ? '<div class="cfg-linhas">' + linhas + "</div>" : vazio) +
    '<div class="acesso-pe"><button class="primario com-icone" data-acesso-nova="1">' + ic("person_add", 16) + (contas.length ? "Nova conta" : "Criar a conta do titular") + "</button>" +
    '<p class="cfg-explica">Contas se criam, mudam e saem só aqui, neste computador. De fora, ninguém mexe nelas.</p></div>');
}

function cartaoSessoes() {
  const s = acessoCfg.sessoes || [];
  if (!s.length) return cartaoCfg("Sessões abertas de fora", metaCfg("nenhuma"), '<p class="cfg-texto">Ninguém está usando o PAULUS de fora agora.</p>');
  const quando = (t) => new Date(t * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  const linhas = s.map((x) => '<div class="cfg-saida"><span class="fin-data">' + esc(quando(x.ultimo_uso)) + '</span><span class="duas-linhas"><b>' + esc(x.nome) +
    "</b><small>" + esc((x.email_access || "") + " · entrou " + quando(x.criada)) + "</small></span></div>").join("");
  return cartaoCfg("Sessões abertas de fora", metaCfg(plural(s.length, "sessão", "sessões")),
    '<div class="cfg-linhas">' + linhas + "</div>" +
    '<div class="acesso-pe"><button class="perigo" data-acesso-encerrar="1">Encerrar todas as sessões</button>' +
    '<p class="cfg-explica">Quem estiver de fora precisa entrar de novo, com senha e código.</p></div>');
}

/* --------------------------------------------------------- os fluxos */

async function acessoPost(url, corpo, metodo) {
  const r = await fetch(url, { method: metodo || "POST", headers: CFG_JSON, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
  if (!r.ok) throw new Error(await erroDe(r));
  return r.json();
}

function acessoRedesenhar() { mostrarConfig("acesso"); }

/* O cadastro no autenticador: QR, o segredo por extenso e o primeiro codigo.
   O dialogo so fecha com o codigo certo - conta sem autenticador confirmado
   nao entra de fora. */
function acessoAutenticador(conta, dados) {
  return new Promise((resolve) => {
    const html = '<div class="acesso-qr-bloco"><div class="acesso-qr">' + (dados.qr_svg || "") + "</div>" +
      '<div class="acesso-qr-texto"><p>No celular, abra o aplicativo autenticador (Google Authenticator, Microsoft Authenticator, 2FAS…), toque em adicionar e leia o código ao lado.</p>' +
      '<p class="cfg-explica">Sem câmera? Digite a chave:</p><code class="acesso-segredo">' + esc((dados.segredo || "").replace(/(.{4})/g, "$1 ").trim()) + "</code></div></div>";
    const pedido = dialogo({
      titulo: "Cadastrar no autenticador",
      contexto: "Acesso de fora › " + conta.nome,
      html: html,
      campo: { rotulo: "Código de 6 números que aparece no aplicativo", placeholder: "000000", max: 6 },
      confirmar: "Confirmar",
      classe: "acesso-dialogo",
      aoConfirmar: async () => {
        const entrada = document.querySelector("#dialogo-campo");
        const erro = document.querySelector("#acesso-erro-codigo");
        try {
          await acessoPost("/api/acesso/contas/" + conta.id + "/autenticador/confirmar", { codigo: entrada.value });
          if (dialogoAberto) dialogoAberto.fechar({ ok: true });
          resolve(true);
        } catch (err) {
          if (erro) erro.textContent = err.message;
          entrada.select();
        }
      },
      depois: '<p class="acesso-erro" id="acesso-erro-codigo" role="alert"></p>',
    });
    pedido.then((r) => { if (!r) resolve(false); });
  });
}

function acessoMostrarCodigos(conta, codigos) {
  return dialogo({
    titulo: "Códigos de recuperação",
    contexto: "Acesso de fora › " + conta.nome,
    texto: "Guarde estes códigos fora do celular. Cada um entra uma vez no lugar do código do autenticador — para o dia em que o celular sumir.\nEles não aparecem de novo.",
    html: '<div class="acesso-codigos">' + codigos.map((c) => "<code>" + esc(c) + "</code>").join("") + "</div>",
    confirmar: "Guardei",
    semCancelar: true,
  });
}

async function acessoNovaConta() {
  const primeira = !(acessoCfg.contas || []).length;
  const r = await dialogo({
    titulo: primeira ? "Conta do titular" : "Nova conta",
    contexto: "Configurações › Acesso de fora",
    texto: primeira ? "A primeira conta é sempre do titular: cuida das contas e pode aprovar de fora." : "",
    campos: [
      { chave: "nome", rotulo: "Nome", placeholder: "como aparece no registro de acessos" },
      { chave: "email", rotulo: "E-mail", tipo: "email", placeholder: "o mesmo que vai passar pela Cloudflare", obrigatorio: true },
      { chave: "senha", rotulo: "Senha", tipo: "password", dica: "pelo menos 10 caracteres", obrigatorio: true },
      { chave: "repetir", rotulo: "Repita a senha", tipo: "password", obrigatorio: true },
    ],
    marcar: primeira ? null : { rotulo: "Titular (pode aprovar de fora e cuidar das contas)", marcada: false },
    confirmar: "Criar a conta",
  });
  if (!r || !r.ok) return;
  const v = r.valores || {};
  if (v.senha !== v.repetir) { avisoCert("as duas senhas não são iguais", { tom: "erro" }); return; }
  let criada;
  try {
    criada = await acessoPost("/api/acesso/contas", { nome: v.nome, email: v.email, senha: v.senha, papel: r.marcada || primeira ? "titular" : "colaborador" });
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return; }
  const ok = await acessoAutenticador(criada.conta, criada);
  await acessoMostrarCodigos(criada.conta, criada.codigos_recuperacao || []);
  avisoCert(ok ? "conta pronta para entrar de fora" : "conta criada; falta confirmar o autenticador", { tom: ok ? "ok" : "" });
  acessoRedesenhar();
}

function ligarAcesso() {
  const clique = (seletor, fn) => document.querySelectorAll(seletor).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const conta = (id) => (acessoCfg.contas || []).find((c) => c.id === Number(id));
  clique("[data-acesso-nova]", () => acessoNovaConta());
  clique("[data-acesso-confirmar]", async (b) => {
    const c = conta(b.dataset.acessoConfirmar);
    if (!c) return;
    // Confirmar depois pede segredo novo: o anterior nao aparece mais.
    if (!(await confirmar({ titulo: "Cadastrar o autenticador de novo?", contexto: "Acesso de fora › " + c.nome, texto: "O segredo mostrado no cadastro não aparece de novo. Sai um novo, para ler com o celular agora.", confirmar: "Mostrar o novo" }))) return;
    try {
      const d = await acessoPost("/api/acesso/contas/" + c.id + "/autenticador/refazer");
      await acessoAutenticador(c, d);
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  clique("[data-acesso-autenticador]", async (b) => {
    const c = conta(b.dataset.acessoAutenticador);
    if (!c) return;
    if (!(await confirmar({ titulo: "Trocar o autenticador?", contexto: "Acesso de fora › " + c.nome, texto: "Para celular novo ou perdido. O código antigo deixa de valer, e quem estiver de fora com esta conta sai.", confirmar: "Trocar", perigo: true }))) return;
    try {
      const d = await acessoPost("/api/acesso/contas/" + c.id + "/autenticador/refazer");
      await acessoAutenticador(c, d);
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  clique("[data-acesso-codigos]", async (b) => {
    const c = conta(b.dataset.acessoCodigos);
    if (!c) return;
    if (!(await confirmar({ titulo: "Gerar códigos novos?", contexto: "Acesso de fora › " + c.nome, texto: "Os " + plural(c.codigos_restantes, "código", "códigos") + " que restam deixam de valer.", confirmar: "Gerar" }))) return;
    try {
      const d = await acessoPost("/api/acesso/contas/" + c.id + "/recuperacao");
      await acessoMostrarCodigos(c, d.codigos_recuperacao || []);
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  clique("[data-acesso-senha]", async (b) => {
    const c = conta(b.dataset.acessoSenha);
    if (!c) return;
    const r = await dialogo({
      titulo: "Trocar a senha", contexto: "Acesso de fora › " + c.nome,
      texto: "Quem estiver de fora com esta conta sai e entra de novo com a senha nova.",
      campos: [{ chave: "senha", rotulo: "Senha nova", tipo: "password", dica: "pelo menos 10 caracteres" },
        { chave: "repetir", rotulo: "Repita a senha", tipo: "password", obrigatorio: true }],
      confirmar: "Trocar a senha",
    });
    if (!r || !r.ok) return;
    if (r.valores.senha !== r.valores.repetir) { avisoCert("as duas senhas não são iguais", { tom: "erro" }); return; }
    try {
      const d = await acessoPost("/api/acesso/contas/" + c.id + "/senha", { senha: r.valores.senha });
      avisoCert("senha trocada" + (d.sessoes_encerradas ? " · " + plural(d.sessoes_encerradas, "sessão encerrada", "sessões encerradas") : ""), { tom: "ok" });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  clique("[data-acesso-remover]", async (b) => {
    const c = conta(b.dataset.acessoRemover);
    if (!c) return;
    if (!(await confirmar({ titulo: "Remover a conta?", contexto: "Acesso de fora › " + c.nome, texto: c.nome + " deixa de entrar de fora na hora. O registro do que a conta fez continua.", confirmar: "Remover", perigo: true }))) return;
    try {
      await acessoPost("/api/acesso/contas/" + c.id, undefined, "DELETE");
      avisoCert("conta removida", { tom: "ok" });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  clique("[data-acesso-encerrar]", async () => {
    if (!(await confirmar({ titulo: "Encerrar todas as sessões?", contexto: "Configurações › Acesso de fora", texto: "Todo mundo que está de fora sai agora.", confirmar: "Encerrar", perigo: true }))) return;
    try {
      const d = await acessoPost("/api/acesso/sessoes/encerrar");
      avisoCert(plural(d.encerradas, "sessão encerrada", "sessões encerradas"), { tom: "ok" });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  if (typeof ligarTunel === "function") ligarTunel();
}
