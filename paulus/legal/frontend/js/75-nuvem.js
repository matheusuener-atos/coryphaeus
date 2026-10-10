/* A nuvem (src/nuvem.py, src/rotas_nuvem.py): N15 com a chave do escritório e,
   desde a V1-V7 (docs/PLANO-NUVEM.md), o Paulus (nuvem) com o plano.

   - Configurações › Modelos: o cartão "Nuvem" - o provedor; para o Paulus
     (nuvem), ativar com o Google, o plano (tokens restantes, usados, a
     renovação; assinar, recarregar, trocar e cancelar abrem a Atos, que
     cobra desde 10/10/2026); para os outros, a chave. O
     termo e o sim do titular, as funcionalidades, mascarar, pedir a cada
     envio, ligar e o registro de envios.
   - A caixa da pergunta: a pílula "Nuvem", de dentro e de fora, ligada por
     padrão quando a nuvem está ligada para a conversa. Clicar deixa a
     próxima pergunta neste computador.
   - A conversa: o cartão do pedido (quando o titular pediu o sim a cada
     envio) e a linha de onde a resposta foi escrita.

   Nada sai antes do sim do titular, dado uma vez, com o termo lido. */

const nuvemTela = { dados: null, situacao: null, conta: null, erroConta: "", modelos: [], envios: [], aqui: false, guardando: false, plano: "" };

async function carregarNuvem() {
  try {
    const r = await fetch("/api/nuvem/situacao");
    nuvemTela.situacao = r.ok ? await r.json() : null;
  } catch (err) {
    nuvemTela.situacao = null;
  }
  desenharPilulaNuvem();
  return nuvemTela.situacao;
}

function tokens(n) {
  const v = Number(n) || 0;
  if (v >= 1e6) return (Math.round(v / 1e5) / 10).toLocaleString("pt-BR") + " milhões";
  if (v >= 1e4) return Math.round(v / 1e3).toLocaleString("pt-BR") + " mil";
  return v.toLocaleString("pt-BR");
}

function dataNuvem(iso) {
  const d = new Date(iso || "");
  return isNaN(d) ? "" : d.toLocaleDateString("pt-BR");
}

/* O dinheiro e da Atos (atos.dev.br) desde 10/10/2026: assinar, recarregar,
   trocar, cancelar, as faturas e o cartao ficam la. O PAULUS so abre a pagina
   no navegador; o plano e os creditos chegam aqui pela conta (GET /api/ia/conta)
   quando a Atos avisa o Worker que o pagamento foi aprovado. */
const ATOS_ASSINATURAS = "https://atos.dev.br/conta/assinaturas";
const ATOS_FATURAS = "https://atos.dev.br/conta/faturamento";
const ATOS_CONTATO = "contato@atos.dev.br";

function abrirNaAtos(url) { window.open(url, "_blank"); }

/* A recarga e um pacote por plano, so no Pix e so com o plano em dia. */
function linkRecargaAtos(planoId) {
  return "https://atos.dev.br/pavlvs/assinar/?preco=" + encodeURIComponent("pavlvs." + planoId + ".recarga") +
    "&volta=" + encodeURIComponent("https://paulus.ia.br/");
}

/* A assinatura no cartao, que renova todo mes (a unica que se cancela). O ano
   e o mes no Pix sao pagos de uma vez e nao renovam. */
function assinaturaNoCartao(c) {
  return ((c || {}).assinatura || {}).situacao === "authorized" && c.periodo !== "anual" && c.periodo !== "avulso";
}

function abrirRecargaNaAtos(c) {
  const id = ((c || {}).plano || {}).id;
  if (!id) { avisoCert("Não sei o plano desta conta agora: abra de novo depois de ler a conta.", { tom: "erro" }); return; }
  abrirNaAtos(linkRecargaAtos(id));
  nuvemTela.esperando = true;
  avisoCert("Termine a compra na Atos, no Pix; os créditos entram aqui assim que o pagamento for aprovado.");
}

/* Trocar de plano: sem o plano em dia, e so assinar o outro. Com ele em dia,
   a Atos nao troca no meio do periodo pago: na assinatura do cartao, cancela-se
   na Conta Atos (o mes pago vale ate o fim) e assina-se o outro depois; no ano
   ou no mes do Pix, assina-se o outro quando o periodo acabar. */
async function trocarPlanoNaAtos(c, nome) {
  const ate = dataNuvem(c.pago_ate || (c.ciclo || {}).fim);
  if (assinaturaNoCartao(c)) {
    const ok = await confirmar({ titulo: "Trocar para o " + nome + "?", contexto: "Conta Atos",
      texto: "A troca é feita na Conta Atos, em dois passos: cancele a assinatura de agora (o mês pago vale até o fim" + (ate ? ", " + ate : "") +
        ") e, quando ele acabar, assine o " + nome + ". Assim não há cobrança em dobro.",
      confirmar: "Abrir a Conta Atos", cancelar: "Agora não" });
    if (ok) abrirNaAtos(ATOS_ASSINATURAS);
    return;
  }
  await dialogo({ titulo: "Trocar para o " + nome + "?", contexto: "Conta Atos", confirmar: "Entendi", semCancelar: true,
    texto: "O período pago vale até " + (ate || "o fim dele") + " e não renova sozinho. Quando ele acabar, assine o " + nome + " aqui." });
}

async function cancelarNaAtos(c) {
  const ate = dataNuvem((c.ciclo || {}).fim || c.pago_ate);
  const ok = await confirmar({ titulo: "Cancelar a assinatura?", contexto: "Conta Atos",
    texto: "A assinatura é cancelada na Conta Atos, em atos.dev.br. Nada mais é cobrado, e o mês pago vale até o fim" + (ate ? " (" + ate + ")" : "") +
      "; depois, o Paulus segue sem a IA da nuvem. Os seus documentos e conversas ficam neste computador.",
    confirmar: "Abrir a Conta Atos", cancelar: "Manter" });
  if (!ok) return;
  abrirNaAtos(ATOS_ASSINATURAS);
  nuvemTela.esperando = true;
}

/* ------------------------------------------------------------ Configurações › Modelos */

function painelDoPlano(d) {
  const prov = (d.provedores || []).find((p) => p.id === "paulus") || {};
  if (!prov.tem_chave) {
    // A conta vinculada pode ser a Conta Google ou a Conta Atos (09/10): ativar abre o navegador nela.
    const porAtos = typeof vincPorAtos === "function" && vincPorAtos();
    return '<div class="cfg-servico"><span class="duas-linhas cresce"><b>Conta da nuvem</b><small>A conta é a conta vinculada a este Paulus. ' +
      (porAtos ? "Ativar abre a Atos para confirmar" : "Ativar abre o Google para confirmar") + "; nada sai antes do sim do titular.</small></span>" +
      '<button class="primario com-icone" data-nuvem-ativar="1">' + ic("login", 16) + (porAtos ? "Ativar com a Atos" : "Ativar com o Google") + "</button></div>";
  }
  const c = nuvemTela.conta;
  if (!c) {
    return '<div class="cfg-servico"><span class="duas-linhas cresce"><b>Plano</b><small>' +
      esc(nuvemTela.erroConta || "carregando…") + '</small></span><button data-nuvem-conta="1">Ver de novo</button></div>';
  }
  const t = c.tokens || {};
  const a = c.assinatura || {};
  const ciclo = c.ciclo || {};
  const situacao = c.cortesia ? "cortesia" : (a.situacao === "authorized" ? "assinatura ativa" : a.situacao === "cancelled" ? "assinatura cancelada"
    : a.situacao === "pending" ? "pagamento esperando a aprovação" : a.situacao === "paused" ? "assinatura pausada"
    : a.situacao === "expired" ? "período pago acabou" : "sem assinatura");
  const vigente = c.plano_vigente;
  const linhas = [];
  linhas.push('<div class="nuvem-plano"><div class="nuvem-restantes"><span class="nuvem-numero">' + esc(tokens(t.restantes)) + "</span>" +
    "<small>créditos livres agora</small></div>" +
    '<dl class="nuvem-numeros">' +
    "<div><dt>Usados neste ciclo</dt><dd>" + esc(tokens(ciclo.usados || 0)) + " de " + esc(tokens(ciclo.tokens || (c.plano || {}).tokens || 0)) + "</dd></div>" +
    (c.semana ? "<div><dt>Nesta semana</dt><dd>" + esc(tokens(c.semana.usados || 0)) + " de " + esc(tokens(c.semana.limite || 0)) + "</dd></div>" : "") +
    "<div><dt>Hoje</dt><dd>" + esc(tokens(t.hoje || 0)) + "</dd></div>" +
    "<div><dt>Da recarga</dt><dd>" + esc(tokens(t.da_recarga || 0)) + "</dd></div>" +
    "<div><dt>" + (c.periodo === "anual" ? "Ano pago até" : c.periodo === "avulso" ? "Pago no Pix até" : a.situacao === "authorized" ? "Renova em" : "Vale até") + "</dt><dd>" +
    esc((c.periodo === "anual" || c.periodo === "avulso") && c.pago_ate ? dataNuvem(c.pago_ate) : vigente && ciclo.fim ? dataNuvem(ciclo.fim) : "—") + "</dd></div>" +
    "</dl></div>");
  const nomeDoPlano = (c.plano || {}).nome ? " · plano " + c.plano.nome : "";
  linhas.push('<p class="cfg-explica">' + esc(c.email) + esc(nomeDoPlano) + " · " + esc(situacao) +
    (vigente ? "" : " · sem o plano em dia, o Paulus funciona sem IA") +
    ". A cota é por semana e não acumula; a recarga não vence na renovação e é gasta depois da cota. Os detalhes estão em Plano e consumo.</p>");
  const botoes = [];
  if (!c.cortesia) {
    // Os tres planos (worker/ia.js): sem o plano em dia, o escolhido vai no
    // checkout da Atos; com ele em dia, a troca e na Atos (trocarPlanoNaAtos).
    const planos = c.planos || [];
    const vale = c.plano || {};
    if (!nuvemTela.plano) nuvemTela.plano = vale.id || "escritorio";
    const escolhido = planos.find((p) => p.id === nuvemTela.plano) || c.plano || {};
    if (planos.length > 1) {
      linhas.push('<div class="nuvem-planos" role="radiogroup" aria-label="Plano">' + planos.map((p) =>
        '<button type="button" class="nuvem-plano-op' + (p.id === escolhido.id ? " on" : "") + '" role="radio" aria-checked="' + (p.id === escolhido.id) +
        '" data-nuvem-plano="' + esc(p.id) + '"><b>' + esc(p.nome) + "</b><span>R$ " + esc(String(p.valor)) + "/mês</span><small>" +
        esc(tokens(p.tokens)) + " créditos por mês · " + esc(((p.modelos_info || [])[0] || {}).nome || "") + "</small></button>").join("") + "</div>");
    }
    if (!vigente) {
      botoes.push('<button class="primario" data-nuvem-assinar="1">Assinar o ' + esc(escolhido.nome || "plano") + " · R$ " + esc(String(escolhido.valor || "")) + "/mês</button>");
      botoes.push('<button data-nuvem-assinar="anual">Anual · R$ ' + esc(String(escolhido.valor_anual || "")) + " (pago de uma vez)</button>");
    } else if (escolhido.id && escolhido.id !== vale.id) {
      botoes.push('<button class="primario" data-nuvem-trocar="1">Trocar para o ' + esc(escolhido.nome) + "</button>");
    }
  }
  if (vigente && !c.cortesia) botoes.push('<button class="com-icone" data-nuvem-recarga="1">' + ic("payments", 16) + "Recarregar " + esc(tokens((c.recarga || {}).tokens)) + " créditos" +
    " · R$ " + esc(String((c.recarga || {}).valor || "")) + " no Pix</button>");
  // Depois de abrir a Atos (ou com o pagamento ainda pendente), conferir lê a conta de novo.
  if (nuvemTela.esperando || a.situacao === "pending") botoes.push('<button data-nuvem-conferir="1">Já paguei na Atos</button>');
  if (assinaturaNoCartao(c)) botoes.push('<button class="perigo" data-nuvem-cancelar="1">Cancelar a assinatura</button>');
  botoes.push('<button data-nuvem-sair="1">Desligar esta instalação da conta</button>');
  linhas.push('<div class="linha-form">' + botoes.join("") + "</div>");
  return linhas.join("");
}

function blocoDoSim(d) {
  if (d.consentido) {
    const s = d.consentimento || {};
    return '<div class="cfg-servico"><span class="duas-linhas cresce"><b>O sim do titular</b><small>dado por ' + esc(s.quem || "titular") + " em " +
      esc(dataNuvem(s.quando)) + " · termo de " + esc(s.versao) + "</small></span>" +
      '<button data-nuvem-termo="1">Ler o termo</button><button class="perigo" data-nuvem-retirar="1">Retirar o sim</button></div>';
  }
  return '<div class="cfg-servico nuvem-sem-sim"><span class="duas-linhas cresce"><b>Antes de ligar: o termo</b><small>O titular lê o que sai, para onde vai ' +
    "e o que nunca vai, e dá o sim. Sem ele, nada sai deste computador.</small></span>" +
    '<button class="primario" data-nuvem-termo="1">Ler o termo e dar o sim</button></div>';
}

function cartaoNuvem() {
  const d = nuvemTela.dados;
  if (!d) return "";
  const prov = (d.provedores || []).find((p) => p.id === d.provedor) || (d.provedores || [])[0] || {};
  const ehPaulus = d.provedor === "paulus";
  const opProv = (d.provedores || []).map((p) =>
    '<option value="' + esc(p.id) + '"' + (p.id === d.provedor ? " selected" : "") + ">" + esc(p.nome) +
    (p.tem_chave ? (p.assinatura ? " · ativada" : " · chave guardada") : "") + "</option>").join("");
  const lista = nuvemTela.modelos.length ? nuvemTela.modelos : (d.modelo ? [d.modelo] : []);
  const opMod = lista.map((m) => '<option value="' + esc(m) + '"' + (m === d.modelo ? " selected" : "") + ">" + esc(m) + "</option>").join("");
  const estadoTxt = d.ligada ? "ligada" + (d.pedir_cada_envio ? " · cada envio espera o seu sim" : " · vai sem pedir, com o sim do titular")
    : (!d.consentido ? "falta o sim do titular" : d.ligado ? "falta ativar ou escolher o modelo" : "desligada");
  const tarefas = Object.entries(d.nomes_tarefas || {}).map(([id, nome]) =>
    '<label class="cfg-servico"><span class="duas-linhas cresce"><b>' + esc(nome) + "</b></span>" +
    '<input type="checkbox" data-nuvem-tarefa="' + esc(id) + '"' + ((d.tarefas || {})[id] ? " checked" : "") + "></label>").join("");
  const envios = nuvemTela.envios.slice(0, 8).map((e) =>
    '<div class="cfg-servico"><span class="caixa-tipo">' + ic("upload", 18) + '</span><span class="duas-linhas cresce"><b>' +
    esc((e.titulo || "pergunta").slice(0, 80)) + "</b><small>" + esc(dataHoraCurta(e.quando)) + " · " + esc(e.modelo) + " · " +
    milhar(e.caracteres || 0) + " caracteres" + (e.tokens_entrada ? " · " + milhar(e.tokens_entrada) + " + " + milhar(e.tokens_saida || 0) + " tokens" : "") +
    " · " + esc(e.como || "") + "</small></span>" +
    '<button data-nuvem-envio="' + esc(e.envio) + '">Ver o que saiu</button></div>').join("");
  const explica = ehPaulus
    ? '<p class="cfg-texto">O <b>Paulus (nuvem)</b> escreve as respostas no modelo do plano do escritório: Llama 3.3 70B no Advogado, Mistral Large 3 no Escritório e Claude Sonnet 5.5 (com o Claude Opus 5.5 no nível Ministro) no Escritório Plus. ' +
      "A busca, as regras, a conferência e o resto do programa continuam neste computador; só o texto da pergunta vai e volta.</p>"
    : '<p class="cfg-texto">A resposta pode ser escrita por um modelo do provedor, com a <b>chave de API do próprio escritório</b> (paga pelo escritório, ' +
      "direto no provedor). A assinatura de consumidor (ChatGPT Plus, Claude Pro) não serve: os termos proíbem usar o login dela num programa.</p>";
  const chave = ehPaulus ? "" :
    '<div class="linha-form"><input type="password" id="nuvem-chave" autocomplete="off" spellcheck="false" placeholder="' +
    (prov.tem_chave ? "chave guardada · cole outra para trocar" : (d.provedor === "anthropic" ? "sk-ant-…" : "cole a chave de API")) + '">' +
    '<button data-nuvem-guardar="1"' + (nuvemTela.guardando ? " disabled" : "") + ">" + (nuvemTela.guardando ? "testando…" : "Guardar e testar") + "</button>" +
    (prov.tem_chave ? '<button class="perigo" data-nuvem-apagar="1">Apagar a chave</button>' : "") + "</div>" +
    (d.dpapi ? "" : '<p class="cfg-explica mod-erro">Este Windows não guarda segredo cifrado (DPAPI): a chave não pode ser guardada.</p>');
  const pronto = prov.tem_chave && d.modelo && d.consentido;
  const corpo = explica +
    '<div class="cfg-linhas">' +
    '<div class="cfg-servico"><span class="duas-linhas cresce"><b>Provedor</b><small>' + esc(estadoTxt) + "</small></span>" +
    '<select id="nuvem-provedor" aria-label="Provedor">' + opProv + "</select></div>" +
    (ehPaulus ? painelDoPlano(d) : chave) +
    (prov.tem_chave ? '<div class="cfg-servico"><span class="duas-linhas cresce"><b>Modelo</b><small>' +
      (ehPaulus ? "o do plano; quem decide é paulus.ia.br, pelo plano e pela profundidade da pergunta" : "a lista é a que a chave enxerga; cobra por token, na conta do escritório") +
      "</small></span>" + (lista.length ? '<select id="nuvem-modelo" aria-label="Modelo da nuvem">' + opMod + "</select>" : "") + "</div>" : "") +
    blocoDoSim(d) +
    '<p class="sv-kicker">O que vai à nuvem</p>' + tarefas +
    '<p class="cfg-explica">Fica sempre neste computador: o e-mail (também a reescrita), o juiz, a leitura do Acervo, o parecer do Financeiro, ' +
    "o anexo guardado do e-mail (desta versão em diante), a cópia das pastas do Drive feita pelo Paulus e o caso marcado só no escritório.</p>" +
    '<label class="cfg-servico"><span class="duas-linhas cresce"><b>Mascarar antes de sair</b><small>CPF, CNPJ, número de processo, e-mail e telefone viram ' +
    "“[CPF 1]”… e voltam na resposta. Reduz a exposição, não anonimiza: o nome, o endereço e o resto do texto vão como estão.</small></span>" +
    '<input type="checkbox" id="nuvem-mascarar"' + (d.mascarar ? " checked" : "") + "></label>" +
    '<label class="cfg-servico"><span class="duas-linhas cresce"><b>Pedir o sim a cada pergunta</b><small>a pergunta espera em Aprovações, com o texto exato que sai; ' +
    "de fora, ela fica neste computador (o sim é dado aqui)</small></span>" +
    '<input type="checkbox" id="nuvem-pedir"' + (d.pedir_cada_envio ? " checked" : "") + "></label>" +
    '<label class="cfg-servico"><span class="duas-linhas cresce"><b>Ligar a nuvem</b><small>' +
    (pronto ? "ligada, as funcionalidades marcadas acima escrevem na nuvem" : "falta " + (!d.consentido ? "o sim do titular" : ehPaulus ? "ativar a conta" : "guardar a chave")) +
    "</small></span>" + '<input type="checkbox" id="nuvem-ligado"' + (d.ligado ? " checked" : "") + (pronto ? "" : " disabled") + "></label>" +
    "</div>" +
    (envios ? '<p class="sv-kicker">Registro de envios · ' + plural(d.envios || 0, "envio") + '</p><div class="cfg-linhas">' + envios + "</div>" : "");
  return cartaoCfg("Nuvem", metaCfg(d.ligada ? "ligada" : "desligada"), corpo, "nuvem-cartao");
}

async function nuvemPost(url, corpo, metodo) {
  const r = await fetch(url, { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: corpo ? JSON.stringify(corpo) : undefined });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  return r.json();
}

async function carregarContaNuvem(forcar) {
  try {
    const r = await fetch("/api/nuvem/paulus/conta" + (forcar ? "?forcar=true" : ""));
    const d = r.ok ? await r.json() : { conta: null, erro: await erroDe(r) };
    nuvemTela.conta = d.conta; nuvemTela.erroConta = d.erro || "";
  } catch (err) { nuvemTela.conta = null; nuvemTela.erroConta = "sem internet agora"; }
}

async function carregarNuvemNaConfig() {
  await carregarNuvem();
  try {
    const r = await fetch("/api/nuvem");
    nuvemTela.dados = r.ok ? await r.json() : null;
  } catch (err) { nuvemTela.dados = null; }
  const d = nuvemTela.dados;
  if (d && d.provedor === "paulus" && ((d.provedores || []).find((p) => p.id === "paulus") || {}).tem_chave) await carregarContaNuvem(false);
  try {
    const r = await fetch("/api/nuvem/envios?limite=8");
    nuvemTela.envios = r.ok ? (await r.json()).envios || [] : [];
  } catch (err) { nuvemTela.envios = []; }
}

async function lerTermoNuvem(redesenhar) {
  const d = nuvemTela.dados;
  const r = await fetch("/api/nuvem/termo?provedor=" + encodeURIComponent(d.provedor));
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const t = await r.json();
  const html = '<div class="nuvem-termo">' + t.texto.map((p) => "<p>" + esc(p) + "</p>").join("") + "</div>";
  if (d.consentido) {
    dialogo({ titulo: "O termo da nuvem", contexto: t.nome + " · versão " + t.versao, classe: "dialogo-ver", larga: true, confirmar: "Fechar", semCancelar: true, html });
    return;
  }
  const res = await dialogo({ titulo: "Antes de ligar a nuvem", contexto: t.nome + " · versão " + t.versao, larga: true, html,
    marcar: { rotulo: "Sou o titular do escritório, li o termo e dou o sim" }, confirmar: "Dar o sim", cancelar: "Agora não" });
  if (!res || !res.ok) return;
  if (!res.marcada) { avisoCert("Para dar o sim, marque que leu o termo.", { tom: "erro" }); return; }
  const novo = await nuvemPost("/api/nuvem/consentimento", { aceito: true, versao: t.versao });
  if (novo) { nuvemTela.dados = novo; avisoCert("Sim registrado. Agora dá para ligar a nuvem.", { tom: "ok" }); await carregarNuvem(); redesenhar(); }
}

async function ativarNuvemPaulus(redesenhar) {
  const tentar = async () => {
    const r = await fetch("/api/nuvem/paulus/ativar", { method: "POST" });
    if (r.status === 401) return false;
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return true; }
    const d = await r.json();
    nuvemTela.dados = d; nuvemTela.conta = d.conta; nuvemTela.erroConta = d.erro || "";
    avisoCert("Nuvem ativada para " + ((d.conta || {}).email || "esta conta") + ".", { tom: "ok" });
    redesenhar();
    return true;
  };
  if (await tentar()) return;
  const quem = typeof vincPorAtos === "function" && vincPorAtos() ? "a Atos" : "o Google";
  if (typeof entrarNoGoogleDoVinculo !== "function") { avisoCert("Vincule este Paulus a uma conta antes (Configurações › Conta).", { tom: "erro" }); return; }
  let feito = false;
  try {
    await entrarNoGoogleDoVinculo("confirmar", async () => {
      const e = (typeof vinc !== "undefined" && vinc.estado) || {};
      if (feito || e.finalidade !== "confirmar") return;
      if (e.fase === "pronto") { feito = true; await tentar(); }
      else if (e.fase === "erro" || e.fase === "cancelado") { feito = true; avisoCert(e.mensagem || "não deu para entrar com " + quem, { tom: "erro" }); }
    });
    avisoCert("Entre com " + quem + " no navegador que abriu.");
  } catch (err) { avisoCert(err.message, { tom: "erro" }); }
}

function ligarNuvemNaConfig(raiz, redesenhar) {
  desenharPilulaNuvem();
  if (!raiz || !nuvemTela.dados) return;
  const d = nuvemTela.dados;
  const clique = (sel, f) => { const b = raiz.querySelector(sel); if (b) b.onclick = f; };
  const prov = raiz.querySelector("#nuvem-provedor");
  if (prov) prov.onchange = async () => {
    nuvemTela.modelos = [];
    const novo = await nuvemPost("/api/nuvem/configurar", { provedor: prov.value, modelo: "", ligado: false });
    if (novo) { nuvemTela.dados = novo; if (novo.provedor === "paulus") await carregarContaNuvem(false); redesenhar(); }
  };
  clique("[data-nuvem-guardar]", async () => {
    const chave = (raiz.querySelector("#nuvem-chave").value || "").trim();
    if (!chave) { avisoCert("Cole a chave de API do provedor.", { tom: "erro" }); return; }
    nuvemTela.guardando = true; redesenhar();
    const r = await nuvemPost("/api/nuvem/chave", { provedor: (prov && prov.value) || d.provedor, chave: chave });
    nuvemTela.guardando = false;
    if (r) {
      nuvemTela.dados = r; nuvemTela.modelos = r.modelos || [];
      avisoCert("Chave guardada e testada: a conta enxerga " + plural(nuvemTela.modelos.length, "modelo") + ".", { tom: "ok" });
    }
    redesenhar();
  });
  clique("[data-nuvem-apagar]", async () => {
    const r = await nuvemPost("/api/nuvem/chave/" + encodeURIComponent(d.provedor), null, "DELETE");
    if (r) { nuvemTela.dados = r; nuvemTela.modelos = []; avisoCert("Chave apagada deste computador.", { tom: "ok" }); }
    redesenhar();
  });
  clique("[data-nuvem-ativar]", () => ativarNuvemPaulus(redesenhar));
  clique("[data-nuvem-conta]", async () => { await carregarContaNuvem(true); redesenhar(); });
  clique("[data-nuvem-termo]", () => lerTermoNuvem(redesenhar));
  clique("[data-nuvem-retirar]", async () => {
    const res = await dialogo({ titulo: "Retirar o sim?", texto: "A nuvem desliga na hora, e as respostas voltam a ser escritas neste computador. Para ligar de novo, o titular lê o termo e dá o sim outra vez.",
      confirmar: "Retirar o sim", perigo: true });
    if (!res || !res.ok) return;
    const r = await nuvemPost("/api/nuvem/consentimento", { aceito: false });
    if (r) { nuvemTela.dados = r; await carregarNuvem(); redesenhar(); }
  });
  raiz.querySelectorAll("[data-nuvem-plano]").forEach((b) => {
    b.onclick = () => { nuvemTela.plano = b.dataset.nuvemPlano; redesenhar(); };
  });
  clique("[data-nuvem-trocar]", async () => {
    const c = nuvemTela.conta || {};
    const destino = (c.planos || []).find((p) => p.id === nuvemTela.plano) || {};
    await trocarPlanoNaAtos(c, destino.nome || "outro plano");
    redesenhar();
  });
  raiz.querySelectorAll("[data-nuvem-assinar]").forEach((b) => { b.onclick = async () => {
    const anual = b.dataset.nuvemAssinar === "anual";
    const r = await nuvemPost("/api/nuvem/paulus/assinar", { plano: nuvemTela.plano, periodo: anual ? "anual" : "mensal" });
    if (!r) return;
    if (!r.link) { avisoCert("paulus.ia.br não devolveu o endereço do pagamento na Atos", { tom: "erro" }); return; }
    abrirNaAtos(r.link);
    nuvemTela.esperando = true;
    avisoCert("Termine na Atos, na página que abriu, com a Conta Atos: no cartão ou no Pix" + (anual ? ", o ano de uma vez." : ".") +
      " O plano aparece aqui assim que o pagamento for aprovado.");
    redesenhar();
  }; });
  clique("[data-nuvem-conferir]", async () => {
    await carregarContaNuvem(true);
    if (nuvemTela.conta && nuvemTela.conta.plano_vigente) nuvemTela.esperando = false;
    redesenhar();
  });
  clique("[data-nuvem-cancelar]", async () => { await cancelarNaAtos(nuvemTela.conta || {}); redesenhar(); });
  clique("[data-nuvem-recarga]", () => { abrirRecargaNaAtos(nuvemTela.conta); redesenhar(); });
  clique("[data-nuvem-sair]", async () => {
    const res = await dialogo({ titulo: "Desligar esta instalação?", texto: "O segredo desta instalação é apagado daqui e de paulus.ia.br. A conta e o plano continuam; para usar de novo, ative outra vez.",
      confirmar: "Desligar", perigo: true });
    if (!res || !res.ok) return;
    const r = await nuvemPost("/api/nuvem/chave/paulus", null, "DELETE");
    if (r) { nuvemTela.dados = r; nuvemTela.conta = null; await carregarNuvem(); redesenhar(); }
  });
  const modelo = raiz.querySelector("#nuvem-modelo");
  if (modelo) {
    modelo.onfocus = async () => {
      if (nuvemTela.modelos.length) return;
      const r = await fetch("/api/nuvem/modelos?provedor=" + encodeURIComponent(d.provedor));
      if (r.ok) { nuvemTela.modelos = (await r.json()).modelos || []; redesenhar(); }
    };
    modelo.onchange = async () => { const r = await nuvemPost("/api/nuvem/configurar", { modelo: modelo.value }); if (r) { nuvemTela.dados = r; redesenhar(); } };
  }
  const caixa = (sel, campo) => {
    const el = raiz.querySelector(sel);
    if (el) el.onchange = async () => { const r = await nuvemPost("/api/nuvem/configurar", { [campo]: el.checked }); if (r) nuvemTela.dados = r; await carregarNuvem(); redesenhar(); };
  };
  caixa("#nuvem-mascarar", "mascarar");
  caixa("#nuvem-pedir", "pedir_cada_envio");
  caixa("#nuvem-ligado", "ligado");
  raiz.querySelectorAll("[data-nuvem-tarefa]").forEach((el) => {
    el.onchange = async () => {
      const r = await nuvemPost("/api/nuvem/configurar", { tarefas: { [el.dataset.nuvemTarefa]: el.checked } });
      if (r) nuvemTela.dados = r; await carregarNuvem(); redesenhar();
    };
  });
  raiz.querySelectorAll("[data-nuvem-envio]").forEach((b) => {
    b.onclick = async () => {
      const r = await fetch("/api/nuvem/envios/" + encodeURIComponent(b.dataset.nuvemEnvio));
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      const e = await r.json();
      dialogo({ titulo: "O que saiu neste envio", contexto: "Configurações › Modelos › Nuvem", classe: "dialogo-ver", larga: true, confirmar: "Fechar",
        html: '<pre class="nuvem-texto">' + esc(e.texto) + "</pre>" });
    };
  });
}

/* ------------------------------------------------------------ a caixa da pergunta */

function desenharPilulaNuvem() {
  const s = nuvemTela.situacao;
  const pode = Boolean(s && s.ligada);
  let b = document.getElementById("pilula-nuvem");
  if (!pode) { if (b) b.remove(); nuvemTela.aqui = false; return; }
  if (!b) {
    const ditar = document.getElementById("ditar");
    if (!ditar) return;
    b = document.createElement("button");
    b.type = "button";
    b.id = "pilula-nuvem";
    b.className = "pilula pilula-nuvem";
    b.onclick = () => { nuvemTela.aqui = !nuvemTela.aqui; desenharPilulaNuvem(); const p = document.getElementById("pedido"); if (p) p.focus(); };
    ditar.parentNode.insertBefore(b, ditar);
  }
  const vai = !nuvemTela.aqui;
  b.classList.toggle("ativa", vai);
  b.setAttribute("aria-pressed", vai ? "true" : "false");
  b.title = vai
    ? "A próxima pergunta é escrita na nuvem (" + s.nome + ", " + s.modelo + ")" + (s.pedir_cada_envio ? ": o texto que sai aparece antes" : "") +
      ". Clique para escrever esta neste computador."
    : "A próxima pergunta é escrita neste computador. Clique para voltar à nuvem.";
  b.innerHTML = ic(vai ? "cloud_upload" : "desktop_windows", 18) + '<span class="rotulo-botao">' + (vai ? "Nuvem" : "Aqui") + "</span>";
}

/* O que vai junto da pergunta. "Aqui" vale para uma pergunta só. */
function nuvemDoEnvio() {
  const s = nuvemTela.situacao;
  if (!s || !s.ligada) return {};
  const aqui = nuvemTela.aqui;
  nuvemTela.aqui = false;
  desenharPilulaNuvem();
  return aqui ? {} : { nuvem: true };
}

/* ------------------------------------------------------------ a conversa */

function cartaoPedidoNuvem(d) {
  const masc = Object.entries(d.mascarados || {}).map(([t, n]) => n + " " + t).join(", ");
  return '<div class="proposta nuvem-pedido" data-nuvem-pedido="' + esc(d.pedido_id || "") + '">' +
    '<div class="proposta-topo"><span class="rotulo">sai desta máquina</span><b>Mandar à ' + esc(d.provedor) + "?</b></div>" +
    '<p class="explica">Vai para o modelo ' + esc(d.modelo) + ": a pergunta e os trechos de " + plural((d.documentos || []).length, "documento") +
    (d.documentos && d.documentos.length ? " (" + esc(d.documentos.slice(0, 4).join(", ")) + (d.documentos.length > 4 ? "…" : "") + ")" : "") +
    ", " + milhar(d.caracteres || 0) + " caracteres (~" + milhar(d.tokens_aprox || 0) + " tokens). " +
    (d.mascarar ? (masc ? "Mascarados: " + esc(masc) + "." : "Nada para mascarar.") : "Sem mascarar.") +
    " O pedido também está em Aprovações; responder aqui não manda nada.</p>" +
    '<div class="linha-form"><button class="primario com-icone" data-nuvem-mandar="1">' + ic("cloud_upload", 15) + "Mandar</button>" +
    '<button data-nuvem-aqui="1">Responder aqui</button>' +
    '<button data-nuvem-ver="1">Ver o texto exato</button>' +
    '<label class="nuvem-liberar"><input type="checkbox" data-nuvem-liberar="1"> liberar nesta conversa</label></div></div>';
}

async function decidirNuvem(pedidoId, aprovar) {
  const r = await fetch("/api/aprovacoes/decidir", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [pedidoId], aprovar: aprovar }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  return true;
}

function ligarPedidoNuvem(caixa, d, conversaId) {
  const id = d.pedido_id;
  const fechar = (txt) => {
    caixa.querySelectorAll("button, input").forEach((b) => { b.disabled = true; });
    const ex = caixa.querySelector(".explica");
    if (ex && txt) ex.insertAdjacentHTML("afterend", '<p class="nota">' + esc(txt) + "</p>");
  };
  const mandar = caixa.querySelector("[data-nuvem-mandar]");
  if (mandar) mandar.onclick = async () => {
    const lib = caixa.querySelector("[data-nuvem-liberar]");
    if (lib && lib.checked && conversaId) await nuvemPost("/api/trabalhos/" + encodeURIComponent(conversaId) + "/nuvem", { liberada: true });
    if (await decidirNuvem(id, true)) fechar(lib && lib.checked ? "Mandado. As próximas perguntas desta conversa vão sem pedir." : "Mandado.");
  };
  const aqui = caixa.querySelector("[data-nuvem-aqui]");
  if (aqui) aqui.onclick = async () => { if (await decidirNuvem(id, false)) fechar("Nada saiu: a resposta é escrita neste computador."); };
  const ver = caixa.querySelector("[data-nuvem-ver]");
  if (ver) ver.onclick = async () => {
    const r = await fetch("/api/aprovacoes");
    const lista = r.ok ? ((await r.json()).pendentes || []) : [];
    const p = lista.find((x) => x.id === id);
    dialogo({ titulo: "O texto exato que vai sair", contexto: "Conversa › Nuvem", classe: "dialogo-ver", larga: true, confirmar: "Fechar",
      html: '<pre class="nuvem-texto">' + esc(p ? (p.dados || {}).texto_exato || "" : "o pedido já foi decidido") + "</pre>" });
  };
}

/* Os eventos da resposta (js/03-assistente.js). */
function eventoDaNuvem(tipo, d, v) {
  if (tipo === "nuvem_pedido") {
    if (d.precisa_aprovar) {
      if (v.anotar) v.anotar("a pergunta espera o seu sim para ir à " + d.provedor + " (" + d.modelo + ")");
      if (v.linha) v.linha("Esperando o seu sim para mandar à " + d.provedor + "…");
      if (v.resposta) {
        v.resposta.insertAdjacentHTML("afterbegin", cartaoPedidoNuvem(d));
        ligarPedidoNuvem(v.resposta.querySelector(".nuvem-pedido"), d, v.conversaId);
      }
    }
  } else if (tipo === "nuvem_mandando") {
    const c = v.resposta && v.resposta.querySelector(".nuvem-pedido");
    if (c) c.remove();
    if (v.anotar) v.anotar("mandei à " + d.provedor + " (" + d.modelo + ")" + (d.como ? " · " + d.como : ""));
    if (v.linha) v.linha("A " + d.provedor + " está escrevendo…");
  } else if (tipo === "nuvem_fim") {
    const c = v.resposta && v.resposta.querySelector(".nuvem-pedido");
    if (c) c.remove();
    if (d.onde === "computador") {
      if (v.anotar) v.anotar("escrevi neste computador: " + (d.motivo || ""), "atencao");
      if (v.linha) v.linha("Escrevendo neste computador…");
    } else if (v.anotar) {
      v.anotar("a " + (d.provedor || "nuvem") + " escreveu" + (d.tokens_entrada ? " · " + milhar(d.tokens_entrada) + " + " + milhar(d.tokens_saida || 0) + " tokens" : "") +
        (d.incompleta ? " · parou no meio: " + (d.motivo || "") : ""), d.incompleta ? "atencao" : "");
    }
  }
}

/* A linha de "como" da resposta guardada: onde foi escrita. */
function fraseDaNuvem(como) {
  const n = (como || {}).nuvem;
  if (!n) return "";
  if (n.onde === "nuvem") return "escrita na nuvem (" + n.provedor + ", " + n.modelo + ")" + (Object.keys(n.mascarados || {}).length ? ", com dados mascarados" : "");
  return "escrita neste computador: " + (n.motivo || "");
}

document.addEventListener("DOMContentLoaded", () => { setTimeout(carregarNuvem, 400); });
