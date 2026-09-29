/* ---------------------------------------------- acesso de fora: o tunel */
/*
   R7: ligar o acesso de fora. O mesmo bloco serve ao passo "Acesso a
   distancia" do assistente de configuracao (js/23-boas-vindas.js) e a
   Configuracoes › Acesso de fora (js/42-acesso.js desenha a secao; este
   arquivo, o cartao do tunel). Tres etapas, na mesma tela:

     1. o endereco: sugerido a partir do nome do escritorio, editavel, com a
        disponibilidade conferida enquanto a pessoa digita (400 ms entre
        teclas, e so com o acesso ligado - desligado, nada vai ao Worker);
     2. a conta do titular, com o autenticador: nome, e-mail e senha; o QR; um
        codigo para conferir; os codigos de recuperacao para guardar;
     3. confirmar no navegador: o PAULUS abre paulus.ia.br/conectar, mostra o
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
  // Enquanto a pessoa nao mexe no endereco, ele acompanha o nome do escritorio.
  if (d && !conexaoUI.editado && d.sugestao && d.sugestao !== conexaoUI.slug) {
    conexaoUI.slug = d.sugestao;
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
  return cartaoCfg("Ligar o acesso de fora", meta, liberado + blocoConexao());
}

/* ------------------------------------------------ o bloco de conexao */

function etapaConexao(n, titulo, corpo, feita) {
  return '<div class="acesso-etapa' + (feita ? " feita" : "") + '"><div class="acesso-etapa-cabeca"><span class="bv-num-passo">' +
    (feita ? ic("check", 13) : n) + "</span><b>" + titulo + "</b></div>" + corpo + "</div>";
}

function slugOk() {
  return Boolean(conexaoUI.disp && conexaoUI.disp.disponivel === true && conexaoUI.perguntado === conexaoUI.slug);
}

function textoDisponibilidade() {
  const x = conexaoUI.disp;
  if (!conexaoUI.slug) return ["", ""];
  if (!x || conexaoUI.perguntado !== conexaoUI.slug) return ["conferindo…", ""];
  if (x.disponivel === true) return [ic("check_circle", 16) + "disponível", "ok"];
  if (x.disponivel === null) return [ic("error", 16) + esc(x.motivo || "não consegui conferir agora"), "nao"];
  return [ic("close", 16) + esc(x.motivo || "indisponível") +
    (x.sugestao ? ' · <button type="button" class="em-ligacao" data-cx-sugestao="' + esc(x.sugestao) + '">usar ' + esc(x.sugestao) + "</button>" : ""), "nao"];
}

function blocoConexao() {
  const d = tunelCfg.dados || {};
  const s = d.situacao || {};
  const pedido = (d.conexao || {}).pedido;
  const titulares = d.titulares || [];
  const esperando = pedido && pedido.estado === "esperando";

  // 1. O endereco. Durante a espera, fica o que foi pedido.
  const slug = esperando ? pedido.slug : conexaoUI.slug;
  const [disp, tom] = textoDisponibilidade();
  const endereco = etapaConexao(1, "Endereço",
    '<div class="acesso-slug"><input type="text" id="cx-slug" value="' + esc(slug) + '" maxlength="24" spellcheck="false" autocomplete="off"' +
    ' autocapitalize="off" aria-label="Nome do endereço"' + (esperando ? " disabled" : "") + '><span class="acesso-dominio">.paulus.ia.br</span></div>' +
    '<p class="acesso-disp" data-tom="' + tom + '" id="cx-disp" role="status">' + (esperando ? "" : disp) + "</p>" +
    '<div class="acesso-final"><code id="cx-final">' + esc((slug || "…") + ".paulus.ia.br") + "</code>" +
    "<small>você e a sua equipe entram por aqui</small></div>", false);

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
      '<div class="acesso-pe"><button class="primario" data-cx-guardei="1">Guardei os códigos</button></div>';
  } else if (titulares.length) {
    const t = titulares[0];
    conta = '<p class="cfg-texto">' + esc(t.nome) + " · " + esc(t.email) + ' · <span class="fin-meta-ponto ok"><i></i>pronta</span></p>' +
      '<p class="cfg-explica">Entra com o Google e o código do autenticador. As contas da equipe se criam em Configurações › Acesso de fora.</p>';
  } else {
    const v = conexaoUI.conta;
    // Vinculado a conta Google (E5): o e-mail dela e o da conta de titular,
    // fixo; o nome vem do Google. Sobra so o secundario.
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
    const daPessoa = conexaoUI.onde === "bv" && vinculo.email ? (conexaoUI.daPessoa || {}) : null;
    if (daPessoa && daPessoa.nome) {
      v.nome = daPessoa.nome; v.email = vinculo.email; v.secundario = daPessoa.secundario || "";
      conta = '<div class="cfg-linhas">' + chaveCfg("Nome", v.nome) + chaveCfg("E-mail Google", vinculo.email) +
        (v.secundario ? chaveCfg("E-mail secundário", v.secundario) : "") + "</div>" +
        '<p class="cfg-explica">Vêm de Seus dados; dá para mudar lá.</p>' +
        '<p class="acesso-erro" role="alert">' + esc(conexaoUI.erroConta) + "</p>" +
        '<div class="acesso-pe"><button class="primario com-icone" data-cx-criar-conta="1">' + ic("shield_person", 16) + "Criar a conta e ler o QR</button>" +
        '<p class="cfg-explica">Sem ela, ninguém entra de fora. Você entra com o Google e o código do celular; o código fica só neste computador.</p></div>';
    } else conta = '<div class="acesso-form">' + campo("nome", "Nome", "text", "como aparece no registro de acessos") +
      (d.so_google
        ? (vinculo.email
          ? '<div class="ag-campo"><label>E-mail Google</label><div class="acesso-fixo">' + ic("check_circle", 16) + "<span>" + esc(vinculo.email) +
            "</span><small>a conta vinculada a este PAULUS</small></div></div>"
          : campo("email", "E-mail Google", "email", "Gmail ou do Google Workspace")) + campo("secundario", "E-mail secundário (opcional)", "email", "")
        : campo("email", "E-mail", "email", "") + campo("senha", "Senha", "password", "pelo menos 10 caracteres") +
          campo("repetir", "Repita a senha", "password", "")) + "</div>" +
      '<p class="acesso-erro" role="alert">' + esc(conexaoUI.erroConta) + "</p>" +
      '<div class="acesso-pe"><button class="primario com-icone" data-cx-criar-conta="1">' + ic("shield_person", 16) + "Criar a conta e ler o QR</button>" +
      '<p class="cfg-explica">' + (d.so_google ? "Sem ela, ninguém entra de fora. Você entra com o Google e o código do celular; o código fica só neste computador."
        : "Sem ela, ninguém entra de fora. Senha e código ficam só neste computador.") + "</p></div>";
  }
  const contaPronta = titulares.length > 0 && conexaoUI.fase !== "codigos";
  const etapaConta = etapaConexao(2, "Sua conta de titular", conta, contaPronta);

  // 3. Confirmar no navegador.
  const faltas = [];
  if (s.disponivel === false) faltas.push("Este computador não tem como guardar os segredos do acesso de fora com proteção (a proteção de dados do Windows).");
  if (s.cloudflared && !s.cloudflared.basta) {
    faltas.push(s.cloudflared.caminho
      ? "O cloudflared deste computador é antigo (" + s.cloudflared.versao + "); o PAULUS precisa da " + s.cloudflared.minima + " ou mais nova. Reinstale o PAULUS: o instalador traz a versão certa."
      : "Falta o cloudflared, o programa da Cloudflare que abre o túnel. Reinstale o PAULUS: o instalador traz.");
  }
  const erro = (d.conexao || {}).erro;
  let confirmar;
  if (esperando) {
    confirmar = '<p class="cfg-texto">Abri <b>paulus.ia.br/conectar</b> no navegador. Confira se o navegador mostra este mesmo código e clique em Confirmar.</p>' +
      '<div class="acesso-codigo-usuario" aria-label="código">' + esc(pedido.codigo_usuario) + "</div>" +
      '<p class="cfg-explica">Vale até ' + esc(new Date(pedido.expira_em).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })) +
      ". Esta tela confere sozinha a cada 3 segundos.</p>" +
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
  } else {
    const pronto = slugOk() && contaPronta && !faltas.length;
    confirmar = (faltas.length ? '<ul class="acesso-faltas">' + faltas.map((f) => "<li>" + esc(f) + "</li>").join("") + "</ul>" : "") +
      (erro ? '<p class="acesso-erro">' + esc(erro) + "</p>" : "") +
      '<div class="acesso-pe"><button class="primario com-icone" data-cx-conectar="1"' + (pronto ? "" : " disabled") + ">" + ic("link", 16) + "Conectar</button>" +
      '<p class="cfg-explica">O PAULUS abre o navegador em paulus.ia.br/conectar. Nada é criado antes de você confirmar lá.</p></div>';
  }
  return '<div class="acesso-etapas">' + endereco + etapaConta +
    etapaConexao(3, "Confirmar no navegador", confirmar, pedido && pedido.estado === "concluido") + "</div>";
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
    const b = disp.querySelector("[data-cx-sugestao]");
    if (b) b.onclick = () => usarSlug(b.dataset.cxSugestao);
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

async function conectarTunel(deNovo) {
  const d = tunelCfg.dados || {};
  const pedido = (d.conexao || {}).pedido;
  const slug = deNovo && pedido ? pedido.slug : conexaoUI.slug;
  const nome = deNovo && pedido ? pedido.nome : (d.escritorio || (typeof bv !== "undefined" && bv.escritorio) || "");
  try {
    await acessoPost("/api/acesso/tunel/conectar", { nome: nome || slug, slug: slug });
  } catch (err) { avisoCert(err.message, { tom: "erro" }); }
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
    // Primeira vez com o endereco na tela: confere sem esperar tecla.
    if (conexaoUI.slug && conexaoUI.perguntado !== conexaoUI.slug && !slug.disabled) conferirSlug();
  }
  clique("[data-cx-sugestao]", (b) => usarSlug(b.dataset.cxSugestao));
  raiz.querySelectorAll("[data-cx-conta]").forEach((i) => { i.oninput = () => { conexaoUI.conta[i.dataset.cxConta] = i.value; }; });
  clique("[data-cx-criar-conta]", async (b) => {
    const v = conexaoUI.conta;
    raiz.querySelectorAll("[data-cx-conta]").forEach((i) => { v[i.dataset.cxConta] = i.value; });
    conexaoUI.erroConta = "";
    const soGoogle = Boolean((tunelCfg.dados || {}).so_google);
    if (!v.nome.trim() || !v.email.trim()) conexaoUI.erroConta = "diga o nome e o e-mail";
    else if (!soGoogle && v.senha !== v.repetir) conexaoUI.erroConta = "as duas senhas não são iguais";
    if (!conexaoUI.erroConta) {
      b.disabled = true;
      try {
        conexaoUI.criada = await acessoPost("/api/acesso/contas", { nome: v.nome, email: v.email, senha: soGoogle ? "" : v.senha,
          email_secundario: v.secundario || "", papel: "titular" });
        conexaoUI.fase = "autenticador";
        v.senha = ""; v.repetir = "";
      } catch (err) { conexaoUI.erroConta = err.message; }
    }
    redesenhar();
  });
  const codigo = raiz.querySelector("#cx-codigo");
  const confirmarCodigo = async () => {
    conexaoUI.erroCodigo = "";
    try {
      await acessoPost("/api/acesso/contas/" + conexaoUI.criada.conta.id + "/autenticador/confirmar", { codigo: codigo.value });
      conexaoUI.fase = "codigos";
      await carregarTunel();
    } catch (err) { conexaoUI.erroCodigo = err.message; }
    redesenhar();
  };
  if (codigo) {
    codigo.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); confirmarCodigo(); } };
    codigo.focus();
  }
  clique("[data-cx-confirmar-codigo]", confirmarCodigo);
  clique("[data-cx-guardei]", async () => {
    conexaoUI.fase = "";
    conexaoUI.criada = null;
    // Em Configuracoes, o cartao Contas tambem mostra a conta nova.
    if (conexaoUI.onde === "cfg" && typeof carregarAcesso === "function") await carregarAcesso();
    else await carregarTunel();
    redesenhar();
  });
  clique("[data-cx-conectar]", (b) => { b.disabled = true; conectarTunel(Boolean(b.dataset.cxDeNovo)); });
  clique("[data-tunel-abrir]", (b) => window.open(b.dataset.tunelAbrir, "_blank"));
  clique("[data-tunel-cancelar]", async () => { await acessoPost("/api/acesso/tunel/cancelar"); await carregarTunel(); redesenhar(); });
  clique("[data-tunel-copiar]", (b) => copiarTexto(b.dataset.tunelCopiar, "endereço copiado"));
  if (typeof ligarEnergia === "function") ligarEnergia(raiz, redesenhar);
}

/* ------------------------------------------------------- conectado */

function cartaoTunelConectado(s, d) {
  const [rotulo, tom] = TUNEL_ESTADOS[s.estado] || [s.estado, ""];
  const endereco = s.hostname ? "https://" + s.hostname : "";
  const prontas = (acessoCfg.contas || []).filter((c) => c.totp_confirmado).map((c) => c.nome);
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
    '<button class="perigo" data-tunel-remover="1">Remover o acesso de fora</button>' +
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
      if (pedido && pedido.estado === "concluido") avisoCert("acesso de fora conectado", { tom: "ok" });
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
    if (!ligar && !(await confirmar({ titulo: "Desligar o acesso de fora?", contexto: "Configurações › Acesso de fora",
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
    if (!(await confirmar({ titulo: "Remover o acesso de fora?", contexto: "Configurações › Acesso de fora",
      texto: "O endereço sai de paulus.ia.br, o túnel é apagado, e quem estiver de fora sai. As contas continuam aqui. O nome fica livre: para voltar, é conectar de novo.",
      confirmar: "Remover", perigo: true }))) return;
    try { await acessoPost("/api/acesso/tunel/remover"); avisoCert("acesso de fora removido", { tom: "ok" }); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    conexaoUI.editado = false;
    await depois();
  });
  acompanharTunel();
}

/* R9: a maquina de pe. O PAULUS segura o Windows acordado enquanto o acesso
   de fora esta ligado; o "abrir com o Windows" (minimizado) e escolha da
   pessoa, desligado de fabrica, e so existe no programa instalado. */
function blocoEnergia(e) {
  if (!e || e.pode_abrir_com_windows === undefined) return "";
  const sub = e.pode_abrir_com_windows
    ? "Sugerido: ao ligar o computador, o PAULUS abre minimizado e o acesso de fora volta sozinho."
    : "Disponível no PAULUS instalado.";
  return '<div class="acesso-energia">' +
    ligaCfg("", "Abrir o PAULUS com o Windows", sub, e.abrir_com_windows, !e.pode_abrir_com_windows)
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
