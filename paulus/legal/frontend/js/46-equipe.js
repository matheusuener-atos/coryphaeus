/* ------------------------------------------------------------- a equipe */
/*
   Um cadastro so para a equipe (pedido do dono, 29/09/2026): a pessoa mora em
   Cadastros › Equipe, e o acesso ao Paulus - a conta, o convite, as
   permissoes - se liga a ela pelo e-mail. As tres telas que falam da equipe
   usam o que esta aqui:

     - Cadastros › Equipe: a coluna "Acesso ao Paulus" e, na ficha, Convidar
       e Permissoes;
     - Configuracoes › Escritorio e equipe: a lista com os mesmos botoes;
     - Configuracoes › Acesso externo › Convidar pela internet: escolhe alguem
       da equipe - ou uma pessoa nova, que entra em Cadastros tambem.

   So na janela do servidor: de fora, contas e convites nao se mexem.
*/

const eqp = { contas: [], convites: [], equipe: [], soGoogle: false, carregado: false };

async function carregarAcessoDaEquipe() {
  if (typeof acessoDeFora !== "undefined" && !acessoDeFora.local) return;
  try {
    const [c, v, f] = await Promise.all([
      fetch("/api/acesso/contas").then((r) => (r.ok ? r.json() : {})),
      fetch("/api/acesso/convites").then((r) => (r.ok ? r.json() : {})),
      fetch("/api/cadastros?tipo=&termo=&ordem=").then((r) => (r.ok ? r.json() : {})),
    ]);
    eqp.contas = c.contas || [];
    eqp.soGoogle = Boolean(c.so_google);
    eqp.segurancaPadrao = c.seguranca_padrao || "padrao";
    eqp.convites = v.convites || [];
    eqp.equipe = (f.fichas || []).filter((x) => x.tipo === "colaborador" || x.tipo === "socio");
    eqp.carregado = true;
  } catch (err) { eqp.carregado = false; }
}

/* O acesso de uma pessoa, pelo e-mail: conta pronta, conta sem autenticador,
   convite em aberto, ou nada. */
function acessoDoEmail(email) {
  const e = String(email || "").trim().toLowerCase();
  if (!e) return { estado: "sem-email", rotulo: "sem e-mail", tom: "" };
  const conta = eqp.contas.find((c) => c.email === e || (c.email_secundario || "") === e);
  if (conta) {
    if (conta.papel === "titular") return { estado: "titular", rotulo: "titular", tom: "ok", conta };
    return conta.pronta
      ? { estado: "ativo", rotulo: "com acesso", tom: "ok", conta }
      : { estado: "pendente", rotulo: "falta o autenticador", tom: "prazo", conta };
  }
  const convite = eqp.convites.find((x) => x.email === e && x.estado === "aberto");
  if (convite) return { estado: "convidado", rotulo: "convite enviado", tom: "prazo", convite };
  return { estado: "sem", rotulo: "sem acesso", tom: "" };
}

function etiquetaDeAcesso(email) {
  if (!eqp.carregado) return '<small class="cad-zero">—</small>';
  const a = acessoDoEmail(email);
  return '<span class="etiqueta' + (a.tom ? " " + a.tom : "") + '">' + esc(a.rotulo) + "</span>";
}

/* ------------------------------------------------------- o convite */

/* O convite de uma pessoa (da equipe ou nova): a mesma caixa nas quatro
   telas (Cadastros, Escritorio e equipe, Acesso externo, a Equipe de um
   servico). A equipe do escritorio e quem entra no Paulus: pessoa nova so
   entra em Cadastros › Equipe pelo convite, com o vinculo e a funcao.
   `ficha` e a pessoa que ja esta em Cadastros. Devolve a ficha (com o id)
   quando o convite saiu; senao, false. */
async function convidarPessoa(ficha, depois, inicial) {
  // `inicial`: o nome e o e-mail que a conversa ja trouxe (js/89-config-na-conversa.js).
  const ja = inicial || {};
  const pedido = dialogo({
    titulo: ficha ? "Convidar " + ficha.nome : "Convidar alguém novo", contexto: "Equipe › acesso ao Paulus",
    texto: (eqp.soGoogle
      ? "A pessoa recebe um link, entra com a conta Google dela e, se a segurança pedir, liga o Google Authenticator no próprio celular."
      : "A pessoa recebe um link, escolhe a senha e, se a segurança pedir, liga o Google Authenticator no próprio celular.") +
      "\nO e-mail do convite precisa ser o da conta Google da pessoa (Gmail ou Google Workspace)." +
      (ficha ? "" : " Ela também entra em Cadastros › Equipe."),
    campos: [
      { chave: "nome", rotulo: "Nome", valor: ficha ? ficha.nome : (ja.nome || ""), obrigatorio: true },
      { chave: "email", rotulo: "E-mail Google", tipo: "email", valor: ficha ? (ficha.email || "") : (ja.email || ""), placeholder: "com ele a pessoa entra", obrigatorio: true },
      { chave: "secundario", rotulo: "E-mail secundário (opcional)", tipo: "email", placeholder: "outro e-mail de contato", obrigatorio: false },
    ],
    depois: (ficha ? "" : '<div class="dialogo-duas"><div class="dialogo-campo"><label for="eqp-tipo">Vínculo</label><div class="dialogo-caixa">' +
      '<select id="eqp-tipo" data-dialogo-chave="tipo"><option value="colaborador">Colaborador</option><option value="socio">Sócio</option></select></div></div>' +
      '<div class="dialogo-campo"><label for="eqp-funcao">Função (opcional)</label><div class="dialogo-caixa">' +
      '<input id="eqp-funcao" data-dialogo-chave="funcao" placeholder="Advogada, estagiário, perito…" autocomplete="off"></div></div></div>') +
      campoSeguranca("eqp-seg", eqp.segurancaPadrao || "padrao"),
    confirmar: "Gerar o convite",
  });
  ligarCampoSeguranca("eqp-seg");
  const r = await pedido;
  if (!r || !r.ok) return false;
  const v = r.valores;
  let feito;
  try {
    feito = await acessoPost("/api/acesso/convites", { nome: v.nome, email: v.email, email_secundario: v.secundario || "",
      seguranca: v.seguranca || "" });
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return false; }
  // A pessoa nova entra na equipe (Cadastros), e a ficha que ja existia fica
  // com o e-mail Google do convite - e por ele que o acesso se liga a ela.
  let resultado = ficha || null;
  try {
    if (!ficha) {
      resultado = await acessoPost("/api/cadastros", { id: null, dados: {
        tipo: v.tipo === "socio" ? "socio" : "colaborador", nome: v.nome, email: v.email, observacao: v.funcao || "" } });
    } else if ((ficha.email || "").toLowerCase() !== v.email.trim().toLowerCase()) {
      resultado = await acessoPost("/api/cadastros", { id: ficha.id, dados: Object.assign({}, ficha, { email: v.email }) });
    }
  } catch (err) { /* o convite saiu; a ficha fica para depois */ }
  await mostrarConviteCriado(v.nome, v.email, feito.link, v.seguranca === "simples");
  await carregarAcessoDaEquipe();
  if (depois) depois();
  return resultado || true;
}

async function mostrarConviteCriado(nome, email, link, simples) {
  const mensagem = "Olá, " + String(nome || "").split(" ")[0] + "! Este é o seu convite para o Paulus do escritório. " +
    (simples ? "Abra e entre com a sua conta Google (" + email + "): " : eqp.soGoogle ? "Abra no celular, entre com a sua conta Google (" + email + ") e ligue o Google Authenticator: "
      : "Abra no celular, escolha a sua senha e ligue o Google Authenticator: ") + link + " (vale 7 dias, uma vez)";
  const escolha = await dialogo({
    titulo: "Convite pronto", contexto: "Convidar " + nome,
    texto: "Mande este link para " + nome + ". Ele vale 7 dias e uma vez só, e não aparece de novo — se perder, é só convidar outra vez.",
    html: '<code class="acesso-segredo">' + esc(link) + "</code>",
    confirmar: "Mandar pelo WhatsApp", segundo: { rotulo: "Copiar o link" }, cancelar: "Fechar",
  });
  if (escolha && escolha.segundo) copiarTexto(link, "link copiado — cole na conversa com a pessoa");
  else if (escolha && escolha.ok) window.open("https://wa.me/?text=" + encodeURIComponent(mensagem), "_blank");
}

/* Convidar pela internet (Acesso externo e Escritorio e equipe): primeiro a
   equipe que ainda nao tem acesso; depois, alguem novo. */
async function convidarDaEquipe(depois) {
  await carregarAcessoDaEquipe();
  const sem = eqp.equipe.filter((f) => ["sem", "sem-email"].includes(acessoDoEmail(f.email).estado));
  if (!sem.length) { await convidarPessoa(null, depois); return; }
  const html = '<div class="eqp-escolha">' + sem.map((f) =>
    '<button type="button" class="eqp-pessoa" data-eqp-convidar="' + f.id + '"><span class="cad-avatar">' + esc(iniciaisDoRemetente(f.nome)) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(f.nome) + "</b><small>" + esc(f.email || "sem e-mail na ficha") + "</small></span>" + ic("chevron_right", 18) + "</button>").join("") +
    '<button type="button" class="eqp-pessoa" data-eqp-convidar="novo"><span class="cad-avatar">' + ic("person_add", 16) + "</span>" +
    '<span class="duas-linhas"><b>Alguém novo</b><small>entra em Cadastros › Equipe também</small></span>' + ic("chevron_right", 18) + "</button></div>";
  let escolhido = "";
  const aberto = dialogo({ titulo: "Quem você quer convidar?", contexto: "Equipe › acesso ao Paulus", html: html,
    texto: "A equipe que ainda não tem acesso ao Paulus, de Cadastros › Equipe.", confirmar: "Fechar", semCancelar: true, classe: "conta-dialogo" });
  document.querySelectorAll("[data-eqp-convidar]").forEach((b) => b.addEventListener("click", () => {
    escolhido = b.dataset.eqpConvidar;
    if (dialogoAberto) dialogoAberto.fechar(null);
  }));
  await aberto;
  if (!escolhido) return;
  const ficha = escolhido === "novo" ? null : eqp.equipe.find((f) => String(f.id) === escolhido);
  await convidarPessoa(ficha, depois);
}

/* -------------------------------------------- na ficha, em Cadastros */

function blocoAcessoDaPessoa(f) {
  if (typeof acessoDeFora !== "undefined" && !acessoDeFora.local) return "";
  const a = acessoDoEmail(f.email);
  const botao = (dado, icone, rotulo) => '<button type="button" class="com-icone" ' + dado + ">" + ic(icone, 16) + esc(rotulo) + "</button>";
  let texto, acoes = "";
  if (a.estado === "titular") texto = "Titular: cuida das contas e pode tudo, também de fora.";
  else if (a.estado === "ativo") { texto = "Entra no Paulus pela internet com " + a.conta.email + "."; acoes = botao('data-eqp-permissoes="1"', "shield_person", "Permissões"); }
  else if (a.estado === "pendente") texto = "A conta existe, mas falta confirmar o autenticador (em Configurações › Acesso externo).";
  else if (a.estado === "convidado") { texto = "Convite enviado — espera a pessoa abrir o link."; acoes = botao('data-eqp-convite="1"', "send", "Convidar de novo"); }
  else if (a.estado === "sem-email") { texto = "Sem acesso ao Paulus. Para convidar, é preciso o e-mail Google da pessoa."; acoes = botao('data-eqp-convite="1"', "send", "Convidar para o Paulus"); }
  else { texto = "Sem acesso ao Paulus."; acoes = botao('data-eqp-convite="1"', "send", "Convidar para o Paulus"); }
  return '<div class="cad-bloco"><span class="cad-bloco-titulo">Acesso ao Paulus <small>' + esc(a.rotulo) + "</small></span>" +
    '<p class="cad-nota">' + esc(texto) + "</p>" + (acoes ? '<div class="dialogo-acoes">' + acoes + "</div>" : "") + "</div>";
}

function ligarAcessoDaPessoa(raiz, f, depois) {
  const conv = raiz.querySelector("[data-eqp-convite]");
  if (conv) conv.addEventListener("click", async () => { if (dialogoAberto) dialogoAberto.fechar(null); await convidarPessoa(f, depois); });
  const perm = raiz.querySelector("[data-eqp-permissoes]");
  if (perm) perm.addEventListener("click", async () => {
    const a = acessoDoEmail(f.email);
    if (dialogoAberto) dialogoAberto.fechar(null);
    if (a.conta && typeof acessoPermissoes === "function") await acessoPermissoes(a.conta);
    await carregarAcessoDaEquipe();
    if (depois) depois();
  });
}

/* ---------------------------------- Configuracoes › Escritorio e equipe */

function cartaoDaEquipeCfg() {
  if (!eqp.carregado) return "";
  const linhas = eqp.equipe.map((f) => {
    const a = acessoDoEmail(f.email);
    const acao = a.estado === "ativo" ? '<button data-eqp-cfg-permissoes="' + f.id + '">Permissões</button>'
      : (["sem", "sem-email", "convidado"].includes(a.estado) ? '<button data-eqp-cfg-convidar="' + f.id + '">' + (a.estado === "convidado" ? "Convidar de novo" : "Convidar") + "</button>" : "");
    return '<div class="cfg-servico"><span class="cad-avatar">' + esc(iniciaisDoRemetente(f.nome)) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(f.nome) + "</b><small>" + esc([f.tipo === "socio" ? "sócio" : "colaborador", f.email].filter(Boolean).join(" · ")) + "</small></span>" +
      etiquetaDeAcesso(f.email) + '<span class="cfg-botoes">' + acao + "</span></div>";
  }).join("");
  const novo = typeof linhaDoConviteNoLado === "function" ? linhaDoConviteNoLado() : "";
  return cartaoCfg("A equipe", metaCfg(plural(eqp.equipe.length + (novo ? 1 : 0), "pessoa")),
    (linhas || novo ? '<div class="cfg-linhas">' + linhas + novo + "</div>" : '<p class="cfg-texto">Ninguém na equipe ainda.</p>') +
    '<div class="acesso-pe"><button class="primario com-icone" data-eqp-cfg-novo="1">' + ic("send", 16) + "Convidar pela internet</button>" +
    '<button class="com-icone" data-cfg-equipe="1">' + ic("groups", 16) + "Cadastros › Equipe</button>" +
    '<p class="cfg-explica">A equipe mora em Cadastros › Equipe (folha, serviços). O acesso ao Paulus se liga a cada pessoa pelo e-mail Google.</p></div>');
}

function ligarEquipeCfg() {
  const redesenhar = async () => { await carregarAcessoDaEquipe(); if (typeof desenharConfig === "function") desenharConfig(); };
  const clique = (sel, fn) => document.querySelectorAll(sel).forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fn(b); }; });
  const ficha = (id) => eqp.equipe.find((f) => String(f.id) === String(id));
  clique("[data-eqp-cfg-novo]", () => convidarDaEquipe(redesenhar));
  clique("[data-eqp-cfg-convidar]", (b) => convidarPessoa(ficha(b.dataset.eqpCfgConvidar), redesenhar));
  clique("[data-eqp-cfg-permissoes]", async (b) => {
    const a = acessoDoEmail((ficha(b.dataset.eqpCfgPermissoes) || {}).email);
    if (a.conta && typeof acessoPermissoes === "function") await acessoPermissoes(a.conta);
    redesenhar();
  });
}
