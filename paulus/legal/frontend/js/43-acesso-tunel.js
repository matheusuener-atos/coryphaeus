/* ---------------------------------------------- acesso externo: o tunel */
/*
   R7: ligar o acesso externo. O mesmo bloco serve ao passo "Acesso a
   distancia" do assistente de configuracao (js/23-boas-vindas.js) e a
   Configuracoes › Acesso externo (js/42-acesso.js desenha a secao; este
   arquivo, o cartao do tunel). Tres etapas, na mesma tela:

     1. o endereco: sugerido a partir do nome do escritorio, editavel, com a
        disponibilidade conferida enquanto a pessoa digita (400 ms entre
        teclas, e so com o acesso ligado - desligado, nada vai ao Worker);
     2. a conta do titular, com o autenticador: nome, e-mail e senha; o QR; um
        codigo para conferir; os codigos de recuperacao para guardar;
     3. confirmar no navegador: o Paulus abre paulus.ia.br/conectar, mostra o
        codigo XXXX-XXXX e pergunta a cada 3 s. Se vencer, "Tentar de novo"
        usa o mesmo nome.

   Conectado, Configuracoes mostra o endereco, o estado do tunel e Desligar /
   Remover. O instalador abre o programa com --configurar-acesso, e o
   desktop.py poe #acesso no endereco: a tela abre direto aqui.
*/

const tunelCfg = { dados: null, relogio: null };

/* O estado do bloco de conexao: sobrevive aos redesenhos da tela. */
const conexaoUI = {
  slug: "", editado: false, disp: null, relogioDisp: null, perguntado: "",
  conta: { nome: "", email: "", senha: "", repetir: "", secundario: "" }, criada: null, fase: "", erroConta: "", erroCodigo: "",
  redesenhar: null, onde: "",
};

async function carregarTunel() {
  try {
    const r = await fetch("/api/acesso/tunel");
    tunelCfg.dados = r.ok ? await r.json() : null;
  } catch (err) {
    tunelCfg.dados = null;
  }
  const d = tunelCfg.dados;
  // O endereco que ja e desta conta Google (de antes de reinstalar) vem
  // primeiro; senao, enquanto a pessoa nao mexe, ele acompanha o nome do
  // escritorio.
  const proposto = d && ((d.meus || [])[0] || {}).slug || (d && d.sugestao);
  if (d && !conexaoUI.editado && proposto && proposto !== conexaoUI.slug) {
    conexaoUI.slug = proposto;
    conexaoUI.disp = null;
    conexaoUI.perguntado = "";
  }
}

const TUNEL_ESTADOS = {
  conectado: ["conectado", "ok"], ligando: ["ligando", ""], caiu: ["desconectado — tentando de novo", "acc"],
  porta_ocupada: ["indisponível: porta ocupada", "acc"], desligado: ["desligado", ""], nao_conectado: ["não conectado", ""],
  sem_cloudflared: ["falta o cloudflared", "acc"], sem_token: ["falta conectar", "acc"],
  liberado: ["endereço liberado", "acc"],
};

function cartaoTunel() {
  const d = tunelCfg.dados;
  if (!d) return "";
  const s = d.situacao || {};
  if (s.conectado_ao_worker) return cartaoTunelConectado(s, d);
  conexaoUI.onde = "cfg";
  conexaoUI.redesenhar = () => desenharConfig();
  const liberado = s.liberado ? '<p class="acesso-erro">' + esc(s.liberado[0].toUpperCase() + s.liberado.slice(1)) + ".</p>" : "";
  const pedido = (d.conexao || {}).pedido;
  const meta = pedido && pedido.estado === "esperando" ? pontoCfg("esperando a confirmação", "acc") : metaCfg("desligado");
  return cartaoCfg("Ligar o acesso externo", meta, liberado + blocoConexao());
}

/* ------------------------------------------------ o bloco de conexao */

function etapaConexao(n, titulo, corpo, feita, o) {
  // No assistente, so texto ("PASSO 1 — ENDEREÇO"), como o rotulo de passo da tela; em Configuracoes, o circulo numerado.
  // No assistente (desenho de 09/10/2026), cada passo e um cartao e so o da vez fica aberto: o feito encolhe com o
  // resumo (o endereco do passo 1) e o "feito"; o que ainda nao chegou fica so com o rotulo, apagado.
  o = o || {};
  const bv = conexaoUI.onde === "bv";
  const cabeca = bv
    ? "<b>Passo " + n + " — " + titulo + "</b>" + (feita && o.resumo ? '<code class="acesso-resumo">' + esc(o.resumo) + "</code>" : "") +
      (feita ? '<span class="acesso-feita">' + ic("check", 13) + "feito</span>" : "")
    : '<span class="bv-num-passo">' + (feita ? ic("check", 13) : n) + "</span><b>" + titulo + "</b>";
  const fechada = bv && (feita || o.fechada);
  return '<div class="acesso-etapa' + (feita ? " feita" : "") + (bv && o.fechada && !feita ? " fechada" : "") + '"><div class="acesso-etapa-cabeca">' + cabeca + "</div>" +
    (fechada ? "" : corpo) + "</div>";
}

function slugOk() {
  return Boolean(conexaoUI.disp && conexaoUI.disp.disponivel === true && conexaoUI.perguntado === conexaoUI.slug);
}

function textoDisponibilidade() {
  const x = conexaoUI.disp;
  if (!conexaoUI.slug) return ["", ""];
  if (!x || conexaoUI.perguntado !== conexaoUI.slug) return ["conferindo…", ""];
  if (x.disponivel === true && x.retomar) return [ic("check_circle", 16) + "é seu — da sua conta; conectar o traz para este Paulus", "ok"];
  if (x.disponivel === true) return [conexaoUI.onde === "bv" ? "" : ic("check_circle", 16) + "disponível", "ok"];
  // Sem conferir (sem conexao, servidor): nao e o campo, e o aviso fica em texto.
  if (x.disponivel === null) return [ic("error", 16) + esc(x.motivo || "não consegui conferir agora"), "nao"];
  // Ocupado ou fora da regra: e o campo - a borda fica vermelha e o motivo vai
  // so para o leitor de tela (pintarSlug). Ficam as saidas: e meu, usar outro.
  return [(x.confirmar_google ? '<button type="button" class="em-ligacao" data-cx-meu="1">é meu: confirmar a minha conta</button>' : "") +
    (x.sugestao ? (x.confirmar_google ? " · " : "") + '<button type="button" class="em-ligacao" data-cx-sugestao="' + esc(x.sugestao) + '">usar ' + esc(x.sugestao) + "</button>" : ""), "nao"];
}

/* A borda do endereco (js/00-base.js): verde livre, vermelho ocupado, neutro
   enquanto confere ou quando nao deu para conferir. */
function pintarSlug() {
  const campo = $("cx-slug");
  if (!campo || campo.disabled) return;
  const x = conexaoUI.disp;
  const pronto = x && conexaoUI.slug && conexaoUI.perguntado === conexaoUI.slug;
  if (pronto && x.disponivel === true) marcarCampo(campo, "ok");
  else if (pronto && x.disponivel === false) marcarCampo(campo, "erro", x.motivo || "esse endereço não está disponível");
  else marcarCampo(campo, "");
}

function blocoConexao() {
  const d = tunelCfg.dados || {};
  const s = d.situacao || {};
  const pedido = (d.conexao || {}).pedido;
  const titulares = d.titulares || [];
  const esperando = pedido && pedido.estado === "esperando";

  // No assistente, a ordem dos passos: o endereco escolhido ("Usar este endereco"), a conta pronta, a confirmacao.
  const concluido = Boolean(pedido && pedido.estado === "concluido");
  const contaFeita = titulares.length > 0 && conexaoUI.fase !== "codigos";
  const bvPassos = { e1: Boolean(esperando || concluido || (conexaoUI.enderecoUsado && slugOk())) };
  bvPassos.e2 = bvPassos.e1 && contaFeita;

  // 1. O endereco. Durante a espera, fica o que foi pedido.
  const slug = esperando ? pedido.slug : conexaoUI.slug;
  const [disp, tom] = textoDisponibilidade();
  const endereco = etapaConexao(1, conexaoUI.onde === "bv" ? "Endereço URL" : "Endereço",
    '<div class="acesso-slug" data-tom="' + tom + '">' + (conexaoUI.onde === "bv" ? '<span class="acesso-cf-ic" title="Túnel da Cloudflare, com Zero Trust">' + marca("cloudflare", 22) + "</span>" : "") + '<input type="text" id="cx-slug" value="' + esc(slug) + '" maxlength="24" spellcheck="false" autocomplete="off"' +
    ' autocapitalize="off" aria-label="Nome do endereço"' + (esperando ? " disabled" : "") + '><span class="acesso-dominio">.paulus.ia.br</span></div>' +
    '<p class="acesso-disp' + (conexaoUI.onde === "bv" ? " so-leitor" : "") + '" data-tom="' + tom + '" id="cx-disp" role="status">' + (esperando ? "" : disp) + "</p>" +
    '<div class="acesso-final"' + (conexaoUI.onde === "bv" ? ' hidden="hidden"' : "") + '><code id="cx-final">' + esc((slug || "…") + ".paulus.ia.br") + "</code>" +
    "<small>você e a sua equipe entram por aqui</small></div>" + blocoMeus(d, esperando) +
    (conexaoUI.onde === "bv" ? '<div class="acesso-pe"><button type="button" class="bv-g-trilho bv-curto" data-cx-usar-endereco="1"><span class="bv-g-pastilha">Usar este endereço</span></button></div>' : ""),
    bvPassos.e1, { resumo: concluido ? (s.hostname || pedido.endereco || "") : esperando ? (pedido.endereco || pedido.slug + ".paulus.ia.br") : (slug || "") + ".paulus.ia.br" });

  // 2. A conta do titular, com o autenticador.
  let conta;
  if (conexaoUI.fase === "autenticador" && conexaoUI.criada) {
    const c = conexaoUI.criada;
    conta = '<div class="acesso-qr-bloco"><div class="acesso-qr">' + (c.qr_svg || "") + "</div>" +
      '<div class="acesso-qr-texto"><p>No celular, abra o <b>Google Authenticator</b>, toque em <b>+</b> e em <b>Ler código QR</b>, e aponte para o código ao lado.</p>' +
      lojasAutenticador() +
      '<p class="cfg-explica">Sem câmera? Digite a chave:</p><code class="acesso-segredo">' + esc((c.segredo || "").replace(/(.{4})/g, "$1 ").trim()) + "</code></div></div>" +
      '<div class="acesso-form"><div class="ag-campo"><label for="cx-codigo">Código de 6 números que aparece no aplicativo</label>' +
      '<input type="text" id="cx-codigo" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"></div></div>' +
      '<p class="acesso-erro" role="alert">' + esc(conexaoUI.erroCodigo) + "</p>" +
      '<div class="acesso-pe"><button class="primario" data-cx-confirmar-codigo="1">Confirmar o código</button></div>';
  } else if (conexaoUI.fase === "codigos" && conexaoUI.criada) {
    conta = '<p class="cfg-texto">Guarde estes códigos fora do celular. Cada um entra uma vez no lugar do código do autenticador — para o dia em que o celular sumir. Eles não aparecem de novo.</p>' +
      '<div class="acesso-codigos">' + (conexaoUI.criada.codigos_recuperacao || []).map((x) => "<code>" + esc(x) + "</code>").join("") + "</div>" +
      (conexaoUI.onde === "bv"
        ? '<div class="acesso-pe acesso-pe-pontas"><button type="button" class="bv-g-trilho bv-curto" data-cx-guardei="1"><span class="bv-g-pastilha">Guardei os códigos</span></button>' +
          '<button class="com-icone" data-cx-baixar-codigos="1">' + ic("download", 16) + "Baixar .txt</button></div>"
        : '<div class="acesso-pe"><button class="com-icone" data-cx-baixar-codigos="1">' + ic("download", 16) + "Baixar .txt</button>" +
          '<button class="primario" data-cx-guardei="1">Guardei os códigos</button></div>');
  } else if (titulares.length) {
    const t = titulares[0];
    conta = (conexaoUI.onde === "bv"
      ? '<p class="cfg-texto"><span class="fin-meta-ponto ok"><i></i>autenticador configurado</span></p>'
      : '<p class="cfg-texto">' + esc(t.nome) + " · " + esc(t.email) + ' · <span class="fin-meta-ponto ok"><i></i>pronta</span></p>') +
      '<p class="cfg-explica">Entra com a conta (Google ou e-mail e senha) e o código do autenticador. As contas da equipe se criam em Configurações › Acesso externo.</p>';
  } else {
    const v = conexaoUI.conta;
    // Vinculado (E5): o e-mail da conta vinculada e o da conta de titular,
    // fixo; o nome vem da conta. Sobra so o secundario.
    const vinculo = d.vinculo || {};
    if (vinculo.email) {
      v.email = vinculo.email;
      if (!v.nome && vinculo.nome) v.nome = vinculo.nome;
    }
    const campo = (chave, rotulo, tipo, dica) => '<div class="ag-campo"><label for="cx-' + chave + '">' + rotulo + "</label>" +
      '<input type="' + tipo + '" id="cx-' + chave + '" data-cx-conta="' + chave + '" value="' + esc(v[chave] || "") + '"' +
      (dica ? ' placeholder="' + esc(dica) + '"' : "") + (tipo === "password" ? ' autocomplete="new-password"' : "") + "></div>";
    // So o Google (decisao do escritorio): a conta e o e-mail Google, sem
    // senha; o e-mail secundario e so de contato.
    // No assistente, com o vinculo, tudo vem de Seus dados: so o resumo.
    // No assistente, a titularidade ja esta dada (a conta Google que entrou, ou Seus dados): nome e e-mail
    // nao se perguntam - so para convidados, em Configuracoes › Acesso externo. Sobram a senha e o autenticador.
    if (conexaoUI.onde === "bv") {
      const daPessoa = conexaoUI.daPessoa || {};
      if (daPessoa.nome) v.nome = daPessoa.nome;
      if (vinculo.email) v.email = vinculo.email; else if (daPessoa.email) v.email = daPessoa.email;
      v.secundario = daPessoa.secundario || "";
      // Vinculado pelo Google, a senha e a do Google: aqui so o autenticador. Pela conta PAVLVS
      // de e-mail e senha (07/10), a entrada de fora pede uma senha deste computador - pode ser a mesma.
      conta = (vinculo.por === "senha"
        ? '<p class="cfg-texto">Para entrar de fora: o seu e-mail, uma senha e o código de 6 dígitos do aplicativo autenticador do celular. A senha fica só neste computador; pode ser a mesma da sua Conta Atos.</p>' +
          '<div class="acesso-form">' + campo("senha", "Senha para entrar de fora", "password", "pelo menos 10 caracteres") +
          campo("repetir", "Confirmar a senha", "password", "") + "</div>"
        : '<p class="cfg-texto">Para entrar de fora: a sua conta Google e o código de 6 dígitos do aplicativo autenticador do celular.</p>') +
        '<p class="acesso-erro" role="alert">' + esc(conexaoUI.erroConta) + "</p>" +
        '<div class="acesso-pe">' + linhaBotao({ classe: "centro", attrs: ' data-cx-criar-conta="1"', icones: [{ html: '<img src="/img/marcas/authenticator.webp" alt="" width="22" height="22">', classe: "lb-22" }], titulo: "Ler o QR no celular" }) +
        '<p class="cfg-explica">O código fica só neste computador. Sem ele, ninguém entra de fora.</p></div>';
    } else conta = '<div class="acesso-form">' + campo("nome", "Nome", "text", "como aparece no registro de acessos") +
      (d.so_google
        ? (vinculo.email
          ? '<div class="ag-campo"><label>E-mail Google</label><div class="acesso-fixo">' + ic("check_circle", 16) + "<span>" + esc(vinculo.email) +
            "</span><small>a conta vinculada a este Paulus</small></div></div>"
          : campo("email", "E-mail Google", "email", "Gmail ou do Google Workspace")) + campo("secundario", "E-mail secundário (opcional)", "email", "")
        : campo("email", "E-mail", "email", "") + campo("senha", "Senha", "password", "pelo menos 10 caracteres") +
          campo("repetir", "Repita a senha", "password", "")) + "</div>" +
      '<p class="acesso-erro" role="alert">' + esc(conexaoUI.erroConta) + "</p>" +
      '<div class="acesso-pe"><button class="primario com-icone" data-cx-criar-conta="1">' + ic("shield_person", 16) + "Criar a conta e ler o QR</button>" +
      '<p class="cfg-explica">' + (d.so_google ? "Sem ela, ninguém entra de fora. Você entra com o Google e o código do celular; o código fica só neste computador."
        : "Sem ela, ninguém entra de fora. Senha e código ficam só neste computador.") + "</p></div>";
  }
  const contaPronta = titulares.length > 0 && conexaoUI.fase !== "codigos";
  const etapaConta = etapaConexao(2, conexaoUI.onde === "bv" ? "Autenticação" : "Sua conta de titular", conta, contaPronta && (conexaoUI.onde !== "bv" || bvPassos.e1),
    { fechada: !bvPassos.e1 });

  // 3. Confirmar no navegador.
  const faltas = [];
  if (s.disponivel === false) faltas.push("Este computador não tem como guardar os segredos do acesso externo com proteção (a proteção de dados do Windows).");
  if (s.cloudflared && !s.cloudflared.basta) {
    faltas.push(s.cloudflared.caminho
      ? "O cloudflared deste computador é antigo (" + s.cloudflared.versao + "); o Paulus precisa da " + s.cloudflared.minima + " ou mais nova. Reinstale o Paulus: o instalador traz a versão certa."
      : "Falta o cloudflared, o programa da Cloudflare que abre o túnel. Reinstale o Paulus: o instalador traz.");
  }
  const erro = (d.conexao || {}).erro;
  let confirmar;
  if (esperando && conexaoUI.onde === "bv") {
    // No assistente (desenho de 09/10/2026): o codigo, a validade ao lado e o botao que reabre a confirmacao.
    confirmar = '<p class="cfg-texto">Confira se o navegador mostra este mesmo código.' +
      (pedido.retomar ? " O endereço é da sua conta: confirmando, ele passa para este Paulus e o de antes deixa de atender." : "") + "</p>" +
      '<div class="acesso-codigo-linha"><div class="acesso-codigo-usuario" aria-label="código">' + esc(pedido.codigo_usuario) + "</div>" +
      '<span class="cfg-explica">Vale até ' + esc(new Date(pedido.expira_em).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })) + ".</span></div>" +
      (erro ? '<p class="acesso-erro">' + esc(erro) + "</p>" : "") +
      '<div class="acesso-pe"><button type="button" class="bv-g-trilho bv-curto" data-tunel-abrir="' + esc(pedido.url) + '"><span class="bv-g-pastilha">Confirmar no navegador</span></button>' +
      '<button type="button" class="bv-ligacao" data-tunel-cancelar="1">Cancelar</button></div>';
  } else if (esperando) {
    confirmar = '<p class="cfg-texto">Abri <b>paulus.ia.br/conectar</b> no navegador. Confira se o navegador mostra este mesmo código e clique em Confirmar.' +
      (pedido.retomar ? " O endereço é da sua conta Google: confirmando, ele passa para este Paulus e o de antes deixa de atender." : "") + "</p>" +
      '<div class="acesso-codigo-usuario" aria-label="código">' + esc(pedido.codigo_usuario) + "</div>" +
      '<p class="cfg-explica">Vale até ' + esc(new Date(pedido.expira_em).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })) + ".</p>" +
      (erro ? '<p class="acesso-erro">' + esc(erro) + "</p>" : "") +
      '<div class="acesso-pe"><button class="com-icone" data-tunel-abrir="' + esc(pedido.url) + '">' + ic("open_in_new", 16) + "Abrir de novo</button>" +
      '<button data-tunel-cancelar="1">Cancelar</button></div>';
  } else if (pedido && (pedido.estado === "expirado" || pedido.estado === "falhou")) {
    confirmar = '<p class="acesso-erro">' + (pedido.estado === "expirado"
      ? "O código venceu antes da confirmação (dura 15 minutos)."
      : "Não consegui terminar: " + esc(erro || "tente de novo")) + "</p>" +
      '<div class="acesso-pe"><button class="primario com-icone" data-cx-conectar="1" data-cx-de-novo="1">' + ic("refresh", 16) + "Tentar de novo</button>" +
      '<p class="cfg-explica">Com o mesmo endereço: ' + esc(pedido.endereco || "") + ".</p></div>";
  } else if (pedido && pedido.estado === "concluido") {
    const e = "https://" + (s.hostname || pedido.endereco || "");
    confirmar = '<div class="acesso-endereco"><code>' + esc(e) + "</code>" +
      '<button class="com-icone" data-tunel-copiar="' + esc(e) + '">' + ic("content_copy", 16) + "Copiar</button></div>" +
      '<p class="cfg-texto">Pronto: o túnel está ligado. Mande este endereço para quem vai entrar de fora — cada pessoa com a própria conta.</p>' +
      (typeof blocoEnergia === "function" ? blocoEnergia(d.energia || {}) : "");
  } else if (conexaoUI.onde === "bv") {
    const sozinho = bvPassos.e2 && !faltas.length && d.google_recente && !conexaoUI.autoPedido;
    confirmar = (faltas.length ? '<ul class="acesso-faltas">' + faltas.map((f) => "<li>" + esc(f) + "</li>").join("") + "</ul>" : "") +
      (erro ? '<p class="acesso-erro">' + esc(erro) + "</p>" : "") +
      (sozinho
        ? '<p class="cfg-texto" data-cx-auto="1">Gerando o código de confirmação…</p>'
        : '<div class="acesso-pe"><button type="button" class="bv-g-trilho bv-curto" data-cx-conectar="1"' + (bvPassos.e2 && !faltas.length ? "" : " disabled") +
          '><span class="bv-g-pastilha">Confirmar no navegador</span></button></div>');
  } else {
    const pronto = slugOk() && contaPronta && !faltas.length;
    confirmar = (faltas.length ? '<ul class="acesso-faltas">' + faltas.map((f) => "<li>" + esc(f) + "</li>").join("") + "</ul>" : "") +
      (erro ? '<p class="acesso-erro">' + esc(erro) + "</p>" : "") +
      '<div class="acesso-pe"><button class="primario com-icone" data-cx-conectar="1"' + (pronto ? "" : " disabled") + ">" + ic("link", 16) +
      (conexaoUI.disp && conexaoUI.disp.retomar ? "Retomar o endereço" : "Conectar") + "</button>" +
      '<p class="cfg-explica">O Paulus abre o navegador em paulus.ia.br/conectar. Nada é criado antes de você confirmar lá.' +
      (d.google_recente ? "" : ((d.vinculo || {}).por === "senha" ? " Antes, a senha da sua Conta Atos confirma que é você" : " Antes, o Google confirma a sua conta") +
        ": o endereço fica dela, e você o retoma se reinstalar.") + "</p></div>";
  }
  return '<div class="acesso-etapas">' + endereco + etapaConta +
    etapaConexao(3, "Confirmar no navegador", confirmar, concluido, { fechada: !bvPassos.e2 }) + "</div>";
}

/* Os enderecos que ja sao desta conta (reinstalou, trocou de computador):
   conectar um deles o traz para este Paulus. */
function blocoMeus(d, esperando) {
  const meus = (d.meus || []).filter((m) => m.slug !== conexaoUI.slug);
  if (esperando || !meus.length) return "";
  return '<p class="cfg-explica">Da sua conta: ' + meus.map((m) =>
    '<button type="button" class="em-ligacao" data-cx-sugestao="' + esc(m.slug) + '">' + esc(m.slug) + ".paulus.ia.br</button>").join(" · ") + "</p>";
}

/* Entrar de novo com a conta vinculada so para provar ao Worker de quem e o
   endereco; volta e segue com `depois`. Pelo Google, o navegador abre; pela
   conta PAVLVS de e-mail e senha, um dialogo pede a senha. */
async function confirmarComGoogle(depois) {
  if (typeof vincPorSenha === "function" && vincPorSenha()) {
    if (!(await confirmarComSenha())) return;
    await carregarTunel();
    conexaoUI.disp = null;
    conexaoUI.perguntado = "";
    if (depois) await depois();
    else conexaoUI.redesenhar && conexaoUI.redesenhar();
    return;
  }
  let feito = false;
  try {
    await entrarNoGoogleDoVinculo("confirmar", async () => {
      const e = vinc.estado || {};
      if (feito || e.finalidade !== "confirmar") return;
      if (e.fase === "pronto") {
        feito = true;
        await carregarTunel();
        conexaoUI.disp = null;
        conexaoUI.perguntado = "";
        if (depois) await depois();
        else conexaoUI.redesenhar && conexaoUI.redesenhar();
      } else if (e.fase === "erro" || e.fase === "cancelado") {
        feito = true;
        avisoCert(e.mensagem || "não deu para entrar com o Google", { tom: "erro" });
      }
    });
    avisoCert("Entre com o Google no navegador que abriu (" + ((tunelCfg.dados || {}).vinculo || {}).email + ").");
  } catch (err) { avisoCert(err.message, { tom: "erro" }); }
}

/* A disponibilidade, 400 ms depois da ultima tecla. So o texto e o botao
   mudam: redesenhar a tela tiraria o cursor do campo. */
function conferirSlug() {
  clearTimeout(conexaoUI.relogioDisp);
  const pedido = conexaoUI.slug;
  if (!pedido) return;
  conexaoUI.relogioDisp = setTimeout(async () => {
    let x;
    try {
      const r = await fetch("/api/acesso/tunel/disponivel?nome=" + encodeURIComponent(pedido));
      x = r.ok ? await r.json() : { disponivel: null, motivo: await erroDe(r) };
    } catch (err) { x = { disponivel: null, motivo: "não consegui conferir agora" }; }
    if (pedido !== conexaoUI.slug) return;
    conexaoUI.disp = x;
    conexaoUI.perguntado = pedido;
    atualizarSlugNaTela();
  }, 400);
}

function atualizarSlugNaTela() {
  const final = $("cx-final");
  if (final) final.textContent = (conexaoUI.slug || "…") + ".paulus.ia.br";
  const disp = $("cx-disp");
  if (disp) {
    const [html, tom] = textoDisponibilidade();
    disp.innerHTML = html;
    disp.dataset.tom = tom;
    const caixa = disp.previousElementSibling;
    if (caixa && caixa.classList.contains("acesso-slug")) caixa.dataset.tom = tom;
    pintarSlug();
    const b = disp.querySelector("[data-cx-sugestao]");
    if (b) b.onclick = () => usarSlug(b.dataset.cxSugestao);
    const meu = disp.querySelector("[data-cx-meu]");
    if (meu) meu.onclick = () => confirmarComGoogle(() => { conexaoUI.redesenhar && conexaoUI.redesenhar(); });
  }
  const d = tunelCfg.dados || {};
  const faltas = (d.situacao || {}).cloudflared && !d.situacao.cloudflared.basta;
  const botao = document.querySelector("[data-cx-conectar]:not([data-cx-de-novo])");
  if (botao) botao.disabled = !(slugOk() && (d.titulares || []).length && conexaoUI.fase !== "codigos" && !faltas);
}

function usarSlug(slug) {
  conexaoUI.slug = slug;
  conexaoUI.editado = true;
  const campo = $("cx-slug");
  if (campo) campo.value = slug;
  conexaoUI.disp = null;
  atualizarSlugNaTela();
  conferirSlug();
}

async function conectarTunel(deNovo, abrir) {
  const d = tunelCfg.dados || {};
  const pedido = (d.conexao || {}).pedido;
  const slug = deNovo && pedido ? pedido.slug : conexaoUI.slug;
  const nome = deNovo && pedido ? pedido.nome : (d.escritorio || (typeof bv !== "undefined" && bv.escritorio) || "");
  // O endereco nasce da conta vinculada: sem login recente, confirmar antes.
  if (!d.google_recente) { await confirmarComGoogle(() => conectarTunel(deNovo, abrir)); return; }
  try {
    await acessoPost("/api/acesso/tunel/conectar", { nome: nome || slug, slug: slug, abrir: abrir !== false });
  } catch (err) {
    if (/confirme a sua conta/.test(err.message)) { await confirmarComGoogle(() => conectarTunel(deNovo, abrir)); return; }
    avisoCert(err.message, { tom: "erro" });
  }
  await carregarTunel();
  conexaoUI.redesenhar && conexaoUI.redesenhar();
  acompanharTunel();
}

function ligarBlocoConexao(raiz) {
  const clique = (seletor, fn) => raiz.querySelectorAll(seletor).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const redesenhar = () => conexaoUI.redesenhar && conexaoUI.redesenhar();
  const slug = raiz.querySelector("#cx-slug");
  if (slug) {
    slug.oninput = () => {
      const limpo = slug.value.toLowerCase().replace(/\s+/g, "-");
      if (limpo !== slug.value) slug.value = limpo;
      conexaoUI.slug = limpo;
      conexaoUI.editado = true;
      conexaoUI.disp = null;
      atualizarSlugNaTela();
      conferirSlug();
    };
    pintarSlug();
    // Primeira vez com o endereco na tela: confere sem esperar tecla.
    if (conexaoUI.slug && conexaoUI.perguntado !== conexaoUI.slug && !slug.disabled) conferirSlug();
  }
  clique("[data-cx-sugestao]", (b) => usarSlug(b.dataset.cxSugestao));
  clique("[data-cx-usar-endereco]", () => {
    if (!slugOk()) {
      const campo = raiz.querySelector("#cx-slug");
      if (campo) { marcarCampo(campo, "erro", "escolha um endereço disponível", raiz.querySelector(".acesso-slug")); campo.focus(); }
      return;
    }
    conexaoUI.enderecoUsado = true;
    redesenhar();
  });
  raiz.querySelectorAll(".acesso-etapa.feita .acesso-resumo").forEach((r) => {
    const pedido = ((tunelCfg.dados || {}).conexao || {}).pedido;
    if (pedido && ["esperando", "concluido"].includes(pedido.estado)) return;
    r.title = "Trocar o endereço";
    r.classList.add("trocar");
    r.onclick = () => { conexaoUI.enderecoUsado = false; redesenhar(); };
  });
  clique("[data-cx-meu]", () => confirmarComGoogle(() => { redesenhar(); }));
  raiz.querySelectorAll("[data-cx-conta]").forEach((i) => { i.oninput = () => { conexaoUI.conta[i.dataset.cxConta] = i.value; }; });
  // Cada campo da conta com a sua regra (js/00-base.js): a borda diz se fecha.
  const cxCampo = (chave) => raiz.querySelector('[data-cx-conta="' + chave + '"]');
  vigiarCampo(cxCampo("nome"), REGRA_CAMPO.preenchido, { vazio: "diga o nome" });
  vigiarCampo(cxCampo("email"), REGRA_CAMPO.email, { vazio: "diga o e-mail" });
  vigiarCampo(cxCampo("secundario"), REGRA_CAMPO.email);
  vigiarCampo(cxCampo("senha"), (s) => (s.length < 10 ? "a senha precisa de pelo menos 10 caracteres" : ""), { vazio: "a senha precisa de pelo menos 10 caracteres" });
  vigiarCampo(cxCampo("repetir"), (s) => (s === ((cxCampo("senha") || {}).value || "") ? "" : "as duas senhas não são iguais"), { vazio: "repita a senha" });
  if (cxCampo("senha") && cxCampo("repetir")) cxCampo("senha").addEventListener("input", () => { if (cxCampo("repetir").dataset.campoTocado) pintarCampo(cxCampo("repetir")); });
  clique("[data-cx-criar-conta]", async (b) => {
    const v = conexaoUI.conta;
    raiz.querySelectorAll("[data-cx-conta]").forEach((i) => { v[i.dataset.cxConta] = i.value; });
    conexaoUI.erroConta = "";
    // No assistente, nome e e-mail ja vieram. Vinculado pelo Google, a conta entra pelo Google (sem senha
    // daqui); pela conta PAVLVS de e-mail e senha, a senha de fora e pedida aqui.
    const noBv = conexaoUI.onde === "bv";
    const porSenha = (((tunelCfg.dados || {}).vinculo) || {}).por === "senha";
    const soGoogle = noBv ? !porSenha : Boolean((tunelCfg.dados || {}).so_google);
    const naTela = ["nome", "email", "secundario", "senha", "repetir"].map(cxCampo);
    if (!conferirCampos(naTela)) return;
    // No assistente nome e e-mail nao tem campo: sem eles, o passo Sua conta nao terminou (nao e campo daqui).
    if (!v.nome.trim() || !v.email.trim()) conexaoUI.erroConta = noBv ? "a sua conta ainda não foi reconhecida; volte ao passo Sua conta" : "diga o nome e o e-mail";
    if (!conexaoUI.erroConta) {
      b.disabled = true;
      try {
        conexaoUI.criada = await acessoPost("/api/acesso/contas", { nome: v.nome, email: v.email, senha: soGoogle ? "" : v.senha,
          email_secundario: v.secundario || "", papel: "titular" });
        conexaoUI.fase = "autenticador";
        v.senha = ""; v.repetir = "";
      } catch (err) {
        // O erro que e de um campo (e-mail, senha) pinta o campo; o resto fica no aviso.
        const m = String(err.message || "");
        const alvo = /senha/i.test(m) ? cxCampo("senha") : /e-mail/i.test(m) && !/secund/i.test(m) ? cxCampo("email") : /secund/i.test(m) ? cxCampo("secundario") : null;
        if (alvo) { b.disabled = false; campoErradoPeloServidor(alvo, m); alvo.focus(); return; }
        conexaoUI.erroConta = m;
      }
    }
    redesenhar();
  });
  const codigo = raiz.querySelector("#cx-codigo");
  vigiarCampo(codigo, (v) => REGRA_CAMPO.codigo6(v.replace(/\D/g, "")), { vazio: "o código tem 6 números" });
  const confirmarCodigo = async () => {
    conexaoUI.erroCodigo = "";
    if (!conferirCampos([codigo])) return;
    try {
      await acessoPost("/api/acesso/contas/" + conexaoUI.criada.conta.id + "/autenticador/confirmar", { codigo: codigo.value });
      conexaoUI.fase = "codigos";
      await carregarTunel();
    } catch (err) {
      // O codigo que nao confere e o campo: borda vermelha, sem texto.
      if (/código/i.test(err.message)) { campoErradoPeloServidor(codigo, err.message); codigo.select(); return; }
      conexaoUI.erroCodigo = err.message;
    }
    redesenhar();
  };
  if (codigo) {
    codigo.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); confirmarCodigo(); } };
    codigo.focus();
  }
  clique("[data-cx-confirmar-codigo]", confirmarCodigo);
  clique("[data-cx-baixar-codigos]", () => {
    const c = conexaoUI.criada || {};
    const slug = (conexaoUI.slug || "") + ".paulus.ia.br";
    const texto = "Paulus — códigos de recuperação do acesso externo\n" + slug + " · " + (c.email || "") + "\n" +
      "Gerados em " + new Date().toLocaleString("pt-BR") + "\n\nCada código entra uma vez, no lugar do código do autenticador.\nGuarde fora do celular.\n\n" +
      (c.codigos_recuperacao || []).join("\n") + "\n";
    const blob = new Blob([texto], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "paulus-codigos-de-recuperacao.txt";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  clique("[data-cx-guardei]", async () => {
    conexaoUI.fase = "";
    conexaoUI.criada = null;
    // Em Configuracoes, o cartao Contas tambem mostra a conta nova.
    if (conexaoUI.onde === "cfg" && typeof carregarAcesso === "function") await carregarAcesso();
    else await carregarTunel();
    redesenhar();
  });
  clique("[data-cx-conectar]", (b) => { b.disabled = true; conectarTunel(Boolean(b.dataset.cxDeNovo)); });
  // No assistente, o passo 3 pede o codigo sozinho uma vez (sem abrir o navegador): o botao abre a confirmacao.
  if (raiz.querySelector("[data-cx-auto]") && !conexaoUI.autoPedido) {
    conexaoUI.autoPedido = true;
    conectarTunel(false, false);
  }
  clique("[data-tunel-abrir]", (b) => window.open(b.dataset.tunelAbrir, "_blank"));
  clique("[data-tunel-cancelar]", async () => { await acessoPost("/api/acesso/tunel/cancelar"); await carregarTunel(); redesenhar(); });
  clique("[data-tunel-copiar]", (b) => copiarTexto(b.dataset.tunelCopiar, "endereço copiado"));
  if (typeof ligarEnergia === "function") ligarEnergia(raiz, redesenhar);
}

/* ------------------------------------------------------- conectado */

function cartaoTunelConectado(s, d) {
  const [rotulo, tom] = TUNEL_ESTADOS[s.estado] || [s.estado, ""];
  const endereco = s.hostname ? "https://" + s.hostname : "";
  const prontas = (acessoCfg.contas || []).filter((c) => c.pronta).map((c) => c.nome);
  const energia = d.energia || {};
  const corpo =
    '<div class="acesso-endereco"><code>' + esc(endereco) + "</code>" +
    '<button class="com-icone" data-tunel-copiar="' + esc(endereco) + '">' + ic("content_copy", 16) + "Copiar</button></div>" +
    '<div class="cfg-linhas">' +
    chaveCfg("Túnel", rotulo, tom) +
    chaveCfg("Porta deste computador", String(s.porta || "—")) +
    chaveCfg("cloudflared", ((s.cloudflared || {}).versao || "não encontrado")) +
    (energia.situacao ? chaveCfg("Energia", energia.situacao, energia.tom || "") : "") +
    "</div>" +
    (s.ultimo_erro && s.estado !== "conectado" ? '<p class="cfg-explica">' + esc(s.ultimo_erro) + "</p>" : "") +
    (s.porta_ocupada ? '<p class="acesso-erro">Outro programa está usando a porta ' + esc(String(s.porta)) +
      ". Enquanto isso, ninguém entra de fora — a janela daqui não é afetada.</p>" : "") +
    '<p class="cfg-texto acesso-quem">Entram de fora: ' +
    (prontas.length ? esc(prontas.join(", ")) : "ninguém ainda") + " — cada um com o Google e o código do autenticador. A lista acompanha as contas abaixo.</p>" +
    (typeof blocoEnergia === "function" ? blocoEnergia(energia) : "") +
    '<div class="acesso-pe">' +
    (s.porta_ocupada ? '<button class="primario" data-tunel-porta="1">Usar outra porta</button>' : "") +
    (s.ligado ? '<button class="com-icone" data-tunel-ligar="0">' + ic("pause", 16) + "Desligar</button>"
      : '<button class="primario com-icone" data-tunel-ligar="1">' + ic("play_arrow", 16) + "Ligar</button>") +
    '<button class="perigo" data-tunel-remover="1">Remover o acesso externo</button>' +
    '<p class="cfg-explica">Desligar para o túnel e guarda o endereço. Remover apaga o endereço em paulus.ia.br e tudo o que ficou guardado aqui; o nome fica livre.</p></div>';
  return cartaoCfg("Endereço", pontoCfg(rotulo, tom), corpo);
}

/* Enquanto espera a confirmacao, a tela pergunta de novo a cada 3 s - e so
   redesenha quando algo mudou (o titular confirmou, o codigo venceu). Fora
   da espera, em Configuracoes, olha o tunel a cada 5 s. */
function acompanharTunel() {
  clearInterval(tunelCfg.relogio);
  const aberta = () => (conexaoUI.onde === "bv"
    ? !$("boas-vindas").hidden && typeof passoBv === "function" && passoBv() === "acesso"
    : cfg.secao === "acesso" && Boolean(document.getElementById("cfg-tela")));
  tunelCfg.relogio = setInterval(async () => {
    if (!aberta()) { clearInterval(tunelCfg.relogio); return; }
    const antes = JSON.stringify(tunelCfg.dados);
    await carregarTunel();
    const pedido = ((tunelCfg.dados || {}).conexao || {}).pedido;
    if (JSON.stringify(tunelCfg.dados) !== antes) {
      if (pedido && pedido.estado === "concluido") avisoCert("acesso externo conectado", { tom: "ok" });
      conexaoUI.redesenhar && conexaoUI.redesenhar();
    }
    if (!pedido || pedido.estado !== "esperando") {
      clearInterval(tunelCfg.relogio);
      if (conexaoUI.onde !== "cfg") return;
      tunelCfg.relogio = setInterval(async () => {
        if (!aberta()) { clearInterval(tunelCfg.relogio); return; }
        const velho = JSON.stringify((tunelCfg.dados || {}).situacao);
        await carregarTunel();
        if (JSON.stringify((tunelCfg.dados || {}).situacao) !== velho) desenharConfig();
      }, 5000);
    }
  }, 3000);
}

function ligarTunel() {
  const tela = document.getElementById("cfg-tela") || document;
  const clique = (seletor, fn) => tela.querySelectorAll(seletor).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const depois = async () => { await carregarTunel(); desenharConfig(); };
  conexaoUI.onde = "cfg";
  conexaoUI.redesenhar = () => desenharConfig();
  ligarBlocoConexao(tela);
  clique("[data-tunel-ligar]", async (b) => {
    const ligar = b.dataset.tunelLigar === "1";
    if (!ligar && !(await confirmar({ titulo: "Desligar o acesso externo?", contexto: "Configurações › Acesso externo",
      texto: "Quem estiver de fora sai agora, e o endereço para de responder. Ligar de novo usa o mesmo endereço.", confirmar: "Desligar" }))) return;
    try { await acessoPost("/api/acesso/tunel/ligar", { ligado: ligar }); } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    await depois();
  });
  clique("[data-tunel-porta]", async () => {
    try {
      const r = await acessoPost("/api/acesso/tunel/porta");
      avisoCert("agora na porta " + r.porta, { tom: "ok" });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    await depois();
  });
  clique("[data-tunel-remover]", async () => {
    if (!(await confirmar({ titulo: "Remover o acesso externo?", contexto: "Configurações › Acesso externo",
      texto: "O endereço sai de paulus.ia.br, o túnel é apagado, e quem estiver de fora sai. As contas continuam aqui. O nome fica livre: para voltar, é conectar de novo.",
      confirmar: "Remover", perigo: true }))) return;
    try { await acessoPost("/api/acesso/tunel/remover"); avisoCert("acesso externo removido", { tom: "ok" }); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    conexaoUI.editado = false;
    await depois();
  });
  acompanharTunel();
}

/* R9: a maquina de pe. O Paulus segura o Windows acordado enquanto o acesso
   de fora esta ligado; o "abrir com o Windows" (minimizado) e escolha da
   pessoa, desligado de fabrica, e so existe no programa instalado. */
function blocoEnergia(e) {
  if (!e || e.pode_abrir_com_windows === undefined) return "";
  const sub = e.pode_abrir_com_windows
    ? "Sugerido: ao ligar o computador, o Paulus abre minimizado e o acesso externo volta sozinho."
    : "Disponível no Paulus instalado.";
  return '<div class="acesso-energia">' +
    ligaCfg("", "Abrir o Paulus com o Windows", sub, e.abrir_com_windows, !e.pode_abrir_com_windows)
      .replace('class="ag-toggle', 'data-energia-abrir="1" class="ag-toggle') +
    (e.suspende_bateria_min ? '<p class="cfg-explica">Na bateria, o plano de energia suspende depois de ' +
      e.suspende_bateria_min + " min parado; fechar a tampa ou mandar suspender também desliga o acesso.</p>" : "") +
    "</div>";
}

function ligarEnergia(raiz, redesenhar) {
  (raiz || document).querySelectorAll("[data-energia-abrir]").forEach((b) => {
    b.onclick = async (ev) => {
      ev.stopPropagation();
      if (b.classList.contains("presa")) return;
      try {
        await acessoPost("/api/acesso/energia/abrir-com-windows", { ligado: !b.classList.contains("on") });
      } catch (err) { avisoCert(err.message, { tom: "erro" }); }
      await carregarTunel();
      (redesenhar || desenharConfig)();
    };
  });
}

/* --configurar-acesso (o instalador) chega como #acesso: abre direto aqui. */
function abrirAcessoPeloEndereco() {
  if (location.hash !== "#acesso" || !acessoDeFora.local) return;
  history.replaceState(null, "", location.pathname);
  setTimeout(() => mostrarConfig("acesso"), 600);
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", abrirAcessoPeloEndereco);
else abrirAcessoPeloEndereco();
