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

/* ------------------------------------------- a pagina aberta de fora */
/*
   R3: o que e bloqueado para quem esta de fora (src/acesso/politicas.py)
   nao aparece como botao que da erro. Os destinos inteiros que so existem no
   computador do escritorio ficam no menu, apagados, e abrem uma tela que diz
   por que; o resto das telas recebe 403 do servidor com a mesma frase, que
   aparece na barra de avisos (js/00-acesso.js).
*/
const DESTINOS_SO_NO_ESCRITORIO = new Set([
  "config", "assinar", "certificado", "financeiro", "relatorios", "foco", "conexoes", "organizar",
  "habilidades", "maquina", "apoiar",
]);
const FRASE_SO_NO_ESCRITORIO = "Disponível só no computador do escritório";

function soNoEscritorio(id) {
  return !acessoDeFora.local && DESTINOS_SO_NO_ESCRITORIO.has(id);
}

function telaSoNoEscritorio(d) {
  abrirTela(d.nome);
  $("centro").innerHTML =
    '<div class="catalogo"><div class="adiante-tela">' +
    '<span class="rotulo">' + esc(FRASE_SO_NO_ESCRITORIO) + "</span>" +
    "<h2>" + esc(d.nome) + "</h2>" +
    "<p>Pelo acesso de fora dá para conversar, ler os documentos, redigir e propor na agenda. " +
    esc(d.nome) + " mexe no que só o computador do escritório deve mexer — certificado, arquivos, dinheiro, configurações — e fica lá.</p>" +
    '<div class="linha-form"><button class="primario" data-volta="1">Voltar para a conversa</button></div>' +
    "</div></div>";
  $("centro").querySelector("[data-volta]").onclick = () => { $("nova").click(); marcarDestino("conversa"); };
  atualizarPostura();
}

/* Os itens do menu que so valem no escritorio ficam apagados, com a frase. */
function marcarMenuDeFora() {
  if (acessoDeFora.local) return;
  document.querySelectorAll("[data-destino]").forEach((b) => {
    if (!DESTINOS_SO_NO_ESCRITORIO.has(b.dataset.destino)) return;
    b.classList.add("so-no-escritorio-item");
    b.title = FRASE_SO_NO_ESCRITORIO;
  });
}
acessoDeFora.pronto.then(() => {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", marcarMenuDeFora);
  else marcarMenuDeFora();
});

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
  await carregarAuditoria();
}

/* ------------------------------------------------------ quem acessou */
/*
   R8: o registro de tudo o que aconteceu pelo acesso de fora, com o filtro e
   o PDF. A corrente de hashes diz se alguem editou o arquivo a mao - e a tela
   diz em que linha.
*/
acessoCfg.filtro = { pessoa: "", acao: "", de: "", ate: "" };
acessoCfg.auditoria = null;

function consultaDaAuditoria() {
  const f = acessoCfg.filtro;
  return Object.keys(f).filter((k) => f[k]).map((k) => k + "=" + encodeURIComponent(f[k])).join("&");
}

async function carregarAuditoria() {
  try {
    const r = await fetch("/api/acesso/auditoria?limite=200&" + consultaDaAuditoria());
    acessoCfg.auditoria = r.ok ? await r.json() : null;
  } catch (err) {
    acessoCfg.auditoria = null;
  }
}

function cartaoAuditoria() {
  const a = acessoCfg.auditoria;
  if (!a) return "";
  const f = acessoCfg.filtro;
  const integro = a.integro
    ? pontoCfg("registro íntegro · " + plural(a.linhas_no_arquivo, "linha"), "ok")
    : pontoCfg("alterado à mão na linha " + a.quebra_na_linha, "acc");
  const opcoes = '<option value="">Tudo</option>' + Object.keys(a.acoes || {}).map((k) =>
    '<option value="' + esc(k) + '"' + (f.acao === k ? " selected" : "") + ">" + esc(a.acoes[k]) + "</option>").join("");
  const filtro = '<div class="acesso-filtro">' +
    '<div class="ag-campo"><label>Pessoa ou e-mail</label><input type="text" id="aud-pessoa" value="' + esc(f.pessoa) + '"></div>' +
    '<div class="ag-campo"><label>O que aconteceu</label><select id="aud-acao">' + opcoes + "</select></div>" +
    '<div class="ag-campo"><label>De</label><input type="date" id="aud-de" value="' + esc(f.de) + '"></div>' +
    '<div class="ag-campo"><label>Até</label><input type="date" id="aud-ate" value="' + esc(f.ate) + '"></div></div>';
  const quando = (iso) => { const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }); };
  const linhas = (a.linhas || []).map((l) => '<div class="cfg-saida"><span class="fin-data">' + esc(quando(l.quando)) + "</span>" +
    '<span class="duas-linhas"><b>' + esc((l.pessoa || l.email || "—") + " · " + l.acao_rotulo) + "</b><small>" +
    esc([l.alvo, l.email, l.ip ? "IP " + l.ip : ""].filter(Boolean).join(" · ")) + "</small></span></div>").join("");
  const corpo = filtro +
    '<div class="acesso-pe"><button class="com-icone" data-aud-filtrar="1">' + ic("filter_list", 16) + "Filtrar</button>" +
    '<button class="com-icone" data-aud-pdf="1">' + ic("picture_as_pdf", 16) + "Exportar PDF</button>" +
    '<p class="cfg-explica">' + (a.total > (a.linhas || []).length ? "Mostrando as " + a.linhas.length + " mais recentes de " + a.total + "; o PDF leva todas. " : "") +
    "Guardado neste computador por um ano. O IP é o que a Cloudflare informou.</p></div>" +
    ((a.linhas || []).length ? '<div class="cfg-linhas">' + linhas + "</div>" : '<p class="cfg-texto">Nada registrado' + (consultaDaAuditoria() ? " com este filtro." : " ainda.") + "</p>");
  return cartaoCfg("Quem acessou", integro, corpo);
}

function ligarAuditoria() {
  const clique = (seletor, fn) => document.querySelectorAll(seletor).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const lerFiltro = () => {
    acessoCfg.filtro = {
      pessoa: ($("aud-pessoa") || {}).value || "", acao: ($("aud-acao") || {}).value || "",
      de: ($("aud-de") || {}).value || "", ate: ($("aud-ate") || {}).value || "",
    };
  };
  clique("[data-aud-filtrar]", async () => { lerFiltro(); await carregarAuditoria(); desenharConfig(); });
  clique("[data-aud-pdf]", () => { lerFiltro(); location.href = "/api/acesso/auditoria/pdf?" + consultaDaAuditoria(); });
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
  return aberturaCfg() + ficha + cartaoComoFunciona() + tunel + cartaoContas() + cartaoSessoes() + cartaoAuditoria();
}

/* O que a pessoa precisa saber antes de ligar, dito sem enfeite. E a mesma
   lista do assistente de conexao e da politica de privacidade. */
function cartaoComoFunciona() {
  const itens = [
    ["desktop_windows", "O computador do escritório precisa estar ligado e com o PAULUS aberto. Desligado, o endereço para de responder."],
    ["key", "Os documentos, o índice e o modelo de IA não saem deste computador. O que passa pela internet é a tela e o que se digita nela."],
    ["lan", "O caminho é o túnel da Cloudflare, num endereço paulus.ia.br da conta do Atos. A conexão é criptografada, mas a Cloudflare a abre no meio do caminho para entregá-la; o Atos não roteia, não inspeciona e não registra esse conteúdo."],
    ["verified", "Para entrar, cada pessoa passa pela verificação contra robôs e usa a própria conta do PAULUS: e-mail, senha e o código do autenticador do celular. Vale igual para o titular e para a equipe."],
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
    "</b><small>" + esc([x.email, x.ip].filter(Boolean).join(" · ") + " · entrou " + quando(x.criada)) + "</small></span></div>").join("");
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
      { chave: "email", rotulo: "E-mail", tipo: "email", placeholder: "com ele a pessoa entra de fora", obrigatorio: true },
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
  ligarAuditoria();
}
