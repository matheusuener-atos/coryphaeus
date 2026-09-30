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

/* O nivel da pessoa no modulo do destino (E2, src/acesso/permissoes.py):
   "nao" some do menu; o Financeiro e os Relatorios, fechados de fabrica,
   abrem quando o titular libera. Sem modulo, null. */
function nivelDoDestino(id) {
  const m = (acessoDeFora.permissoes || []).find((x) => (x.destinos || []).includes(id));
  return m ? m.nivel : null;
}

function soNoEscritorio(id) {
  if (acessoDeFora.local || !DESTINOS_SO_NO_ESCRITORIO.has(id)) return false;
  const nivel = nivelDoDestino(id);
  return !nivel || nivel === "nao";
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
    // O que a pessoa nao ve sai do menu (o titular escolhe, por pessoa).
    if (nivelDoDestino(b.dataset.destino) === "nao") { b.hidden = true; return; }
    if (!soNoEscritorio(b.dataset.destino)) return;
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
    acessoCfg.soGoogle = Boolean(d && d.so_google);
    acessoCfg.segurancaPadrao = (d && d.seguranca_padrao) || "padrao";
    acessoCfg.vinculo = (d && d.vinculo) || {};
  } catch (err) {
    acessoCfg.contas = null;
  }
  try {
    const r = await fetch("/api/acesso/convites");
    acessoCfg.convites = r.ok ? (await r.json()).convites : [];
  } catch (err) { acessoCfg.convites = []; }
  if (typeof carregarTunel === "function") await carregarTunel();
  if (typeof carregarAparelhoTitular === "function") await carregarAparelhoTitular();
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
  const prontas = contas.filter((c) => c.pronta).length;
  const ligado = Boolean(((cfg.prefs || {}).preferencias || {}).acesso_remoto && cfg.prefs.preferencias.acesso_remoto.ligado);
  const ficha = fichaCfg([
    ["Acesso de fora", ligado ? "ligado" : "desligado", ligado ? "ok" : ""],
    ["Contas prontas", prontas + " de " + contas.length],
    ["Sessões abertas", String(acessoCfg.sessoes.length)],
  ]);
  const tunel = typeof cartaoTunel === "function" ? cartaoTunel() : "";
  // D5: escrever no aparelho - o que o titular controla (js/62-aparelho-titular.js).
  const aparelho = typeof cartaoAparelhoTitular === "function" ? cartaoAparelhoTitular() : "";
  return aberturaCfg() + ficha + cartaoComoFunciona() + tunel + cartaoContas() + cartaoSegurancaPadrao() + cartaoSessoes() + aparelho + cartaoAuditoria();
}

/* Os niveis de seguranca (acesso/contas.py NIVEIS): o escritorio escolhe,
   conta por conta, quanto pedir na entrada de fora. */
const NIVEIS_SEGURANCA = [
  { id: "reforcada", rotulo: "Reforçada", curto: "Google + código sempre",
    explica: "Conta Google e o código do autenticador em toda entrada, sem lembrar o navegador." },
  { id: "padrao", rotulo: "Padrão (recomendada)", curto: "Google + código",
    explica: "Conta Google e o código do autenticador; a pessoa pode marcar o navegador dela como confiável por 30 dias." },
  { id: "simples", rotulo: "Simples", curto: "só o Google",
    explica: "Só a conta Google, sem autenticador. Mais cômodo e mais fraco: quem abrir o Google da pessoa entra no PAULUS." },
];

function nivelSeguranca(id) {
  return NIVEIS_SEGURANCA.find((n) => n.id === id) || NIVEIS_SEGURANCA[1];
}

/* O campo do nivel, para os dialogos (conta nova, convite, a conta). */
function campoSeguranca(idCampo, atual) {
  const opcoes = NIVEIS_SEGURANCA.map((n) => '<option value="' + n.id + '"' + (n.id === atual ? " selected" : "") + ">" +
    esc(n.rotulo) + "</option>").join("");
  return '<div class="dialogo-campo"><label for="' + idCampo + '">Segurança da entrada de fora</label><div class="dialogo-caixa">' +
    '<select id="' + idCampo + '" data-dialogo-chave="seguranca">' + opcoes + "</select></div>" +
    '<p class="cfg-explica" id="' + idCampo + '-explica">' + esc(nivelSeguranca(atual).explica) + "</p></div>";
}

/* A explicacao embaixo do campo acompanha a escolha. */
function ligarCampoSeguranca(idCampo) {
  const sel = document.getElementById(idCampo);
  const exp = document.getElementById(idCampo + "-explica");
  if (sel && exp) sel.addEventListener("change", () => { exp.textContent = nivelSeguranca(sel.value).explica; });
}

function cartaoSegurancaPadrao() {
  if (!acessoCfg.disponivel || acessoCfg.contas === null) return "";
  const atual = nivelSeguranca(acessoCfg.segurancaPadrao);
  return cartaoCfg("Segurança das contas novas", metaCfg(atual.rotulo.replace(" (recomendada)", "")),
    '<p class="cfg-texto">O nível que o convite e a conta criada aqui já trazem marcado. Cada conta pode ter o seu: em Contas, botão “Segurança”.</p>' +
    '<div class="cfg-linhas">' + NIVEIS_SEGURANCA.map((n) =>
      '<label class="cfg-servico"><input type="radio" name="seg-padrao" value="' + n.id + '"' + (n.id === atual.id ? " checked" : "") +
      ' data-seguranca-padrao="' + n.id + '"><span class="duas-linhas"><b>' + esc(n.rotulo) + "</b><small>" + esc(n.explica) + "</small></span></label>").join("") +
    "</div>");
}

async function acessoSeguranca(c) {
  const pedido = dialogo({
    titulo: "Segurança de " + c.nome, contexto: "Configurações › Acesso de fora",
    texto: "Quanto o PAULUS pede quando " + c.nome + " entra de fora. Na janela deste computador nada muda.",
    depois: campoSeguranca("acc-seg", c.seguranca || "padrao"),
    confirmar: "Salvar",
  });
  ligarCampoSeguranca("acc-seg");
  const r = await pedido;
  if (!r || !r.ok) return;
  const nivel = (r.valores || {}).seguranca || "padrao";
  if (nivel === (c.seguranca || "padrao")) return;
  try {
    const d = await acessoPost("/api/acesso/contas/" + c.id + "/seguranca", { nivel }, "PUT");
    const conta = d.conta || c;
    avisoCert(nivel !== "simples" && !conta.pronta
      ? "segurança salva — falta ligar o autenticador desta conta (botão “Confirmar”)"
      : "segurança de " + c.nome + " salva", { tom: conta.pronta ? "ok" : "" });
  } catch (err) { avisoCert(err.message, { tom: "erro" }); }
  acessoRedesenhar();
}

/* O que a pessoa precisa saber antes de ligar, dito sem enfeite. E a mesma
   lista do assistente de conexao e da politica de privacidade. */
function cartaoComoFunciona() {
  const itens = [
    ["desktop_windows", "O computador do escritório precisa estar ligado e com o PAULUS aberto. Desligado, o endereço para de responder."],
    ["key", "Os documentos, o índice e o modelo de IA não saem deste computador. O que passa pela internet é a tela e o que se digita nela."],
    ["lan", "O caminho é o túnel da Cloudflare, num endereço paulus.ia.br da conta do Atos. A conexão é criptografada, mas a Cloudflare a abre no meio do caminho para entregá-la; o Atos não roteia, não inspeciona e não registra esse conteúdo."],
    ["verified", "Para entrar, cada pessoa passa pela verificação contra robôs e entra com a própria conta Google e, conforme o nível de segurança da conta, o código do autenticador do celular. O nível se escolhe aqui, conta por conta."],
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
    const simples = c.seguranca === "simples";
    const estado = c.pronta
      ? '<span class="fin-meta-ponto ok"><i></i>pronta</span>'
      : '<span class="fin-meta-ponto acc"><i></i>falta o autenticador</span>';
    const sub = c.email + (c.email_secundario ? " · secundário " + c.email_secundario : "") + " · " +
      (c.papel === "titular" ? "titular" : "colaborador") + " · segurança " + nivelSeguranca(c.seguranca).curto +
      (c.totp_confirmado && !simples ? " · " + plural(c.codigos_restantes, "código", "códigos") + " de recuperação" : "");
    return '<div class="cfg-servico"><span class="caixa-tipo">' + ic(c.papel === "titular" ? "shield_person" : "person", 18) + "</span>" +
      '<span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" + esc(sub) + "</small></span>" + estado +
      '<span class="cfg-botoes">' +
      (c.pronta ? "" : '<button data-acesso-confirmar="' + c.id + '">Confirmar</button>') +
      '<button data-acesso-seguranca="' + c.id + '">Segurança</button>' +
      (c.papel === "titular" ? "" : '<button data-acesso-permissoes="' + c.id + '">Permissões</button>') +
      '<button data-acesso-emails="' + c.id + '">E-mails</button>' +
      (acessoCfg.soGoogle ? "" : '<button data-acesso-senha="' + c.id + '">Senha</button>') +
      (simples ? "" : '<button data-acesso-autenticador="' + c.id + '">Autenticador</button>' +
        '<button data-acesso-codigos="' + c.id + '">Códigos</button>') +
      '<button class="mais-linha" data-acesso-remover="' + c.id + '" title="Remover a conta" aria-label="Remover a conta">' + ic("close", 16) + "</button>" +
      "</span></div>";
  }).join("");
  const vazio = '<p class="cfg-texto">Nenhuma conta ainda. A primeira é a do titular: quem cuida das contas e pode aprovar de fora.</p>';
  // Os convites em aberto (E4): a conta nasce no celular de quem foi convidado.
  const quando = (t) => new Date(t * 1000).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  const convites = (acessoCfg.convites || []).filter((x) => x.estado === "aberto").map((x) =>
    '<div class="cfg-servico"><span class="caixa-tipo">' + ic("mail", 18) + "</span>" +
    '<span class="duas-linhas"><b>' + esc(x.nome) + "</b><small>" + esc(x.email) + " · convite enviado · vale até " + esc(quando(x.expira)) + "</small></span>" +
    '<span class="fin-meta-ponto acc"><i></i>aguardando</span>' +
    '<span class="cfg-botoes"><button class="mais-linha" data-convite-revogar="' + esc(x.id) + '" title="Cancelar o convite" aria-label="Cancelar o convite">' +
    ic("close", 16) + "</button></span></div>").join("");
  const titularPronto = contas.some((c) => c.papel === "titular" && c.pronta);
  return cartaoCfg("Contas", metaCfg(contas.length ? plural(contas.length, "conta") : "nenhuma"),
    (contas.length ? '<div class="cfg-linhas">' + linhas + convites + "</div>" : vazio) +
    '<div class="acesso-pe">' +
    (titularPronto
      ? '<button class="primario com-icone" data-convite-novo="1">' + ic("send", 16) + "Convidar pela internet</button>" +
        '<button class="com-icone" data-acesso-nova="1">' + ic("person_add", 16) + "Criar aqui</button>"
      : '<button class="primario com-icone" data-acesso-nova="1">' + ic("person_add", 16) + (contas.length ? "Nova conta" : "Criar a conta do titular") + "</button>") +
    '<p class="cfg-explica">' + (titularPronto
      ? "Convidar manda um link (pelo WhatsApp, por exemplo): a pessoa escolhe a senha e liga o autenticador no próprio celular. As contas só mudam aqui, neste computador."
      : "Contas se criam, mudam e saem só aqui, neste computador. De fora, ninguém mexe nelas.") + "</p></div>");
}

/* O convite (E4): um cadastro so para a equipe (js/46-equipe.js) - escolhe
   alguem de Cadastros › Equipe, ou uma pessoa nova, que entra la tambem. */
async function acessoConvidar() {
  await convidarDaEquipe(acessoRedesenhar);
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

/* O Google Authenticator e o recomendado (gratis, Android e iPhone); outro
   autenticador TOTP tambem serve. Os links abrem a loja no navegador. */
const LOJAS_AUTENTICADOR = [
  ["Android · Google Play", "https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2"],
  ["iPhone · App Store", "https://apps.apple.com/app/google-authenticator/id388497605"],
];

const LOGO_AUTENTICADOR = '<svg viewBox="0 0 48 48" width="28" height="28" aria-hidden="true"><rect x="21" y="4" width="6" height="20" rx="3" fill="#4285F4" transform="rotate(0 24 24)"/><rect x="21" y="4" width="6" height="20" rx="3" fill="#34A853" transform="rotate(60 24 24)"/><rect x="21" y="4" width="6" height="20" rx="3" fill="#FBBC04" transform="rotate(120 24 24)"/><rect x="21" y="4" width="6" height="20" rx="3" fill="#EA4335" transform="rotate(180 24 24)"/><rect x="21" y="4" width="6" height="20" rx="3" fill="#4285F4" transform="rotate(240 24 24)"/><rect x="21" y="4" width="6" height="20" rx="3" fill="#34A853" transform="rotate(300 24 24)"/><circle cx="24" cy="24" r="5" fill="#5F6368"/></svg>';

function lojasAutenticador() {
  return '<div class="acesso-lojas"><div class="acesso-app"><span class="acesso-app-icone">' + LOGO_AUTENTICADOR + "</span>" +
    '<span class="duas-linhas"><b>Google Authenticator</b><small>grátis · gera o código de 6 números do PAULUS</small></span></div>' +
    '<div class="acesso-lojas-botoes">' +
    LOJAS_AUTENTICADOR.map(([rotulo, url]) => '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + ic("download", 16) + esc(rotulo) + "</a>").join("") +
    "</div></div>";
}

/* O cadastro no autenticador: QR, o segredo por extenso e o primeiro codigo.
   O dialogo so fecha com o codigo certo - conta sem autenticador confirmado
   nao entra de fora. */
function acessoAutenticador(conta, dados) {
  return new Promise((resolve) => {
    const html = '<div class="acesso-qr-bloco"><div class="acesso-qr">' + (dados.qr_svg || "") + "</div>" +
      '<div class="acesso-qr-texto"><p>No celular, abra o <b>Google Authenticator</b>, toque em <b>+</b> e em <b>Ler código QR</b>, e aponte para o código ao lado.</p>' +
      lojasAutenticador() +
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
  const pedido = dialogo({
    titulo: primeira ? "Conta do titular" : "Nova conta",
    contexto: "Configurações › Acesso de fora",
    texto: (primeira ? "A primeira conta é sempre do titular: cuida das contas e pode aprovar de fora.\n" : "") +
      "Com a segurança reforçada ou padrão, a pessoa precisa do Google Authenticator no celular: no próximo passo ela lê um QR com ele. Na simples, basta a conta Google.",
    html: lojasAutenticador(),
    depois: campoSeguranca("acc-nova-seg", acessoCfg.segurancaPadrao || "padrao"),
    campos: [
      { chave: "nome", rotulo: "Nome", placeholder: "como aparece no registro de acessos",
        valor: primeira ? ((acessoCfg.vinculo || {}).nome || "") : "" },
      { chave: "email", rotulo: acessoCfg.soGoogle ? "E-mail Google" : "E-mail", tipo: "email",
        valor: primeira ? ((acessoCfg.vinculo || {}).email || "") : "",
        placeholder: acessoCfg.soGoogle ? "Gmail ou do Google Workspace — com ele a pessoa entra" : "com ele a pessoa entra de fora", obrigatorio: true },
      { chave: "secundario", rotulo: "E-mail secundário (opcional)", tipo: "email", placeholder: "outro e-mail de contato", obrigatorio: false },
    ].concat(acessoCfg.soGoogle ? [] : [
      { chave: "senha", rotulo: "Senha", tipo: "password", dica: "pelo menos 10 caracteres", obrigatorio: true },
      { chave: "repetir", rotulo: "Repita a senha", tipo: "password", obrigatorio: true },
    ]),
    marcar: primeira ? null : { rotulo: "Titular (pode aprovar de fora e cuidar das contas)", marcada: false },
    confirmar: "Criar a conta",
  });
  ligarCampoSeguranca("acc-nova-seg");
  const r = await pedido;
  if (!r || !r.ok) return;
  const v = r.valores || {};
  if (!acessoCfg.soGoogle && v.senha !== v.repetir) { avisoCert("as duas senhas não são iguais", { tom: "erro" }); return; }
  let criada;
  try {
    criada = await acessoPost("/api/acesso/contas", { nome: v.nome, email: v.email, senha: v.senha || "",
      email_secundario: v.secundario || "", papel: r.marcada || primeira ? "titular" : "colaborador",
      seguranca: v.seguranca || "" });
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return; }
  if (criada.conta && criada.conta.seguranca === "simples") {
    // Sem autenticador: a conta ja entra so com o Google.
    avisoCert("conta pronta — entra de fora só com a conta Google", { tom: "ok" });
    acessoRedesenhar();
    return;
  }
  const ok = await acessoAutenticador(criada.conta, criada);
  await acessoMostrarCodigos(criada.conta, criada.codigos_recuperacao || []);
  avisoCert(ok ? "conta pronta para entrar de fora" : "conta criada; falta confirmar o autenticador", { tom: ok ? "ok" : "" });
  acessoRedesenhar();
}

/* Quem mexe no que (E2): um nivel por modulo, para esta pessoa. Os dados
   continuam do escritorio; o nivel diz o que ela ve e o que ela grava. */
async function acessoPermissoes(c) {
  let modulos = [];
  try {
    modulos = (await (await fetch("/api/acesso/permissoes/modulos")).json()).modulos || [];
  } catch (err) { avisoCert("não consegui ler os módulos", { tom: "erro" }); return; }
  const escolha = Object.assign({}, c.permissoes || {});
  const linhas = modulos.map((m) => {
    const atual = escolha[m.id] || m.nivel;
    return '<div class="perm-linha"><b>' + esc(m.rotulo) + '</b><span class="perm-niveis" role="radiogroup" aria-label="' + esc(m.rotulo) + '">' +
      m.niveis.map((n) => '<button type="button" class="' + (n.id === atual ? "escolhido" : "") + '" data-perm-modulo="' + m.id +
        '" data-perm-nivel="' + n.id + '" role="radio" aria-checked="' + (n.id === atual) + '">' + esc(n.rotulo) + "</button>").join("") +
      "</span></div>";
  }).join("");
  const pedido = dialogo({
    titulo: "Permissões de " + c.nome, contexto: "Configurações › Acesso de fora", classe: "perm-dialogo", larga: true,
    texto: "O que " + c.nome + " vê e faz pelo acesso de fora. Os dados são do escritório; aqui se escolhe o que cada pessoa alcança.\n" +
      "“Propõe” manda o pedido para Aprovações; “faz” grava direto. Configurações, contas, certificado e apagar arquivos ficam sempre só no computador do escritório.",
    html: '<div class="perm-grade">' + linhas + "</div>",
    confirmar: "Salvar permissões",
    aoConfirmar: async () => {
      try {
        await acessoPost("/api/acesso/contas/" + c.id + "/permissoes", { niveis: escolha }, "PUT");
        if (dialogoAberto) dialogoAberto.fechar({ ok: true });
        avisoCert("permissões de " + c.nome + " salvas — valem já no próximo clique dela", { tom: "ok" });
        acessoRedesenhar();
      } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    },
  });
  document.querySelectorAll("[data-perm-nivel]").forEach((b) => b.addEventListener("click", () => {
    escolha[b.dataset.permModulo] = b.dataset.permNivel;
    document.querySelectorAll('[data-perm-modulo="' + b.dataset.permModulo + '"]').forEach((x) => {
      const sim = x === b;
      x.classList.toggle("escolhido", sim);
      x.setAttribute("aria-checked", String(sim));
    });
  }));
  await pedido;
}

function ligarAcesso() {
  if (typeof ligarAparelhoTitular === "function") ligarAparelhoTitular();
  const clique = (seletor, fn) => document.querySelectorAll(seletor).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b); }; });
  const conta = (id) => (acessoCfg.contas || []).find((c) => c.id === Number(id));
  clique("[data-acesso-nova]", () => acessoNovaConta());
  clique("[data-acesso-seguranca]", (b) => { const c = conta(b.dataset.acessoSeguranca); if (c) acessoSeguranca(c); });
  document.querySelectorAll("[data-seguranca-padrao]").forEach((el) => {
    el.onchange = async () => {
      try {
        await acessoPost("/api/acesso/seguranca-padrao", { nivel: el.value }, "PUT");
        acessoCfg.segurancaPadrao = el.value;
        avisoCert("contas novas: segurança " + nivelSeguranca(el.value).rotulo.toLowerCase(), { tom: "ok" });
      } catch (err) { avisoCert(err.message, { tom: "erro" }); }
      acessoRedesenhar();
    };
  });
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
  clique("[data-convite-novo]", () => acessoConvidar());
  clique("[data-convite-revogar]", async (b) => {
    if (!(await confirmar({ titulo: "Cancelar o convite?", contexto: "Configurações › Acesso de fora",
      texto: "O link deixa de valer na hora. Dá para convidar de novo depois.", confirmar: "Cancelar o convite", perigo: true }))) return;
    try { await acessoPost("/api/acesso/convites/" + b.dataset.conviteRevogar, undefined, "DELETE"); avisoCert("convite cancelado", { tom: "ok" }); }
    catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  clique("[data-acesso-emails]", async (b) => {
    const c = conta(b.dataset.acessoEmails);
    if (!c) return;
    const r = await dialogo({
      titulo: "E-mails de " + c.nome, contexto: "Configurações › Acesso de fora",
      texto: "O e-mail Google é o que entra (Gmail ou do Google Workspace). O secundário é só de contato. Trocar o e-mail Google encerra as sessões da pessoa.",
      campos: [
        { chave: "email", rotulo: "E-mail Google", tipo: "email", valor: c.email, obrigatorio: true },
        { chave: "secundario", rotulo: "E-mail secundário (opcional)", tipo: "email", valor: c.email_secundario || "", obrigatorio: false },
      ],
      confirmar: "Salvar",
    });
    if (!r || !r.ok) return;
    try {
      await acessoPost("/api/acesso/contas/" + c.id, { email: r.valores.email, email_secundario: r.valores.secundario || "" }, "PATCH");
      avisoCert("e-mails salvos", { tom: "ok" });
    } catch (err) { avisoCert(err.message, { tom: "erro" }); }
    acessoRedesenhar();
  });
  clique("[data-acesso-permissoes]", (b) => {
    const c = conta(b.dataset.acessoPermissoes);
    if (c) acessoPermissoes(c);
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
