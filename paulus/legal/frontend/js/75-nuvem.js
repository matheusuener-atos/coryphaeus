/* A nuvem (src/nuvem.py, src/rotas_nuvem.py): N15 com a chave do escritório e,
   desde a V1-V7 (docs/PLANO-NUVEM.md), o PAULUS (nuvem) com o plano.

   - Configurações › Modelos: o cartão "Nuvem" - o provedor; para o PAULUS
     (nuvem), ativar com o Google, o plano (tokens restantes, usados, a
     renovação, assinar, recarregar, cancelar); para os outros, a chave. O
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

/* ------------------------------------------------------------ Configurações › Modelos */

function painelDoPlano(d) {
  const prov = (d.provedores || []).find((p) => p.id === "paulus") || {};
  if (!prov.tem_chave) {
    return '<div class="cfg-servico"><span class="duas-linhas cresce"><b>Conta da nuvem</b><small>A conta é a conta Google vinculada a este PAULUS. ' +
      "Ativar abre o Google para confirmar; nada sai antes do sim do titular.</small></span>" +
      '<button class="primario com-icone" data-nuvem-ativar="1">' + ic("login", 16) + "Ativar com o Google</button></div>";
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
    : a.situacao === "pending" ? "assinatura esperando o cartão" : "sem assinatura");
  const vigente = c.plano_vigente;
  const linhas = [];
  linhas.push('<div class="nuvem-plano"><div class="nuvem-restantes"><span class="nuvem-numero">' + esc(tokens(t.restantes)) + "</span>" +
    "<small>créditos livres agora</small></div>" +
    '<dl class="nuvem-numeros">' +
    "<div><dt>Usados neste ciclo</dt><dd>" + esc(tokens(ciclo.usados || 0)) + " de " + esc(tokens(ciclo.tokens || (c.plano || {}).tokens || 0)) + "</dd></div>" +
    (c.semana ? "<div><dt>Nesta semana</dt><dd>" + esc(tokens(c.semana.usados || 0)) + " de " + esc(tokens(c.semana.limite || 0)) + "</dd></div>" : "") +
    "<div><dt>Hoje</dt><dd>" + esc(tokens(t.hoje || 0)) + "</dd></div>" +
    "<div><dt>Da recarga</dt><dd>" + esc(tokens(t.da_recarga || 0)) + "</dd></div>" +
    "<div><dt>" + (c.periodo === "anual" ? "Ano pago até" : a.situacao === "authorized" ? "Renova em" : "Vale até") + "</dt><dd>" +
    esc(c.periodo === "anual" && c.pago_ate ? dataNuvem(c.pago_ate) : vigente && ciclo.fim ? dataNuvem(ciclo.fim) : "—") + "</dd></div>" +
    "</dl></div>");
  const nomeDoPlano = (c.plano || {}).nome ? " · plano " + c.plano.nome : "";
  linhas.push('<p class="cfg-explica">' + esc(c.email) + esc(nomeDoPlano) + " · " + esc(situacao) +
    (vigente ? "" : " · sem o plano em dia, o PAULUS funciona sem IA") +
    ". A cota é por semana e não acumula; a recarga não vence na renovação e é gasta depois da cota. Os detalhes estão em Plano e consumo.</p>");
  const botoes = [];
  const ativa = a.situacao === "authorized";
  if (ativa && c.plano_proximo) {
    linhas.push('<p class="cfg-explica">Troca marcada: a partir de ' + esc(ciclo.fim ? dataNuvem(ciclo.fim) : "a renovação") + ", o plano " +
      esc(c.plano_proximo.nome) + " (R$ " + esc(String(c.plano_proximo.valor)) + "/mês). O ciclo já pago continua no " + esc((c.plano || {}).nome || "plano de agora") + ".</p>");
  }
  if (!c.cortesia) {
    // Os tres planos (worker/ia.js): sem assinatura, o escolhido vai na
    // assinatura; com ela ativa, vira a troca, que vale na renovacao. O mesmo
    // da pagina paulus.ia.br/cadastro.
    const planos = c.planos || [];
    const vale = (ativa && c.plano_proximo ? c.plano_proximo : c.plano) || {};
    if (!nuvemTela.plano) nuvemTela.plano = vale.id || "escritorio";
    const escolhido = planos.find((p) => p.id === nuvemTela.plano) || c.plano || {};
    if (planos.length > 1) {
      linhas.push('<div class="nuvem-planos" role="radiogroup" aria-label="Plano">' + planos.map((p) =>
        '<button type="button" class="nuvem-plano-op' + (p.id === escolhido.id ? " on" : "") + '" role="radio" aria-checked="' + (p.id === escolhido.id) +
        '" data-nuvem-plano="' + esc(p.id) + '"><b>' + esc(p.nome) + "</b><span>R$ " + esc(String(p.valor)) + "/mês</span><small>" +
        esc(tokens(p.tokens)) + " créditos por mês · " + esc(((p.modelos_info || [])[0] || {}).nome || "") + "</small></button>").join("") + "</div>");
    }
    if (!ativa) {
      botoes.push('<button class="primario" data-nuvem-assinar="1">Assinar o ' + esc(escolhido.nome || "plano") + " · R$ " + esc(String(escolhido.valor || "")) + "/mês</button>");
      botoes.push('<button data-nuvem-assinar="anual">Anual · R$ ' + esc(String(escolhido.valor_anual || "")) + " (até 12×)</button>");
    } else if (escolhido.id && escolhido.id !== vale.id) {
      const desfaz = c.plano_proximo && escolhido.id === (c.plano || {}).id;
      botoes.push('<button class="primario" data-nuvem-trocar="1">' + (desfaz ? "Ficar no " + esc(escolhido.nome) + " (desfazer a troca)"
        : "Trocar para o " + esc(escolhido.nome) + " · R$ " + esc(String(escolhido.valor)) + "/mês na renovação") + "</button>");
    }
  }
  if (vigente) botoes.push('<button class="com-icone" data-nuvem-recarga="1">' + ic("payments", 16) + "Recarregar " + esc(tokens((c.recarga || {}).tokens)) + " créditos" +
    " · R$ " + esc(String((c.recarga || {}).valor || "")) + " no Pix</button>");
  if (a.situacao === "pending") botoes.push('<button data-nuvem-conferir="1">Já pus o cartão</button>');
  if (c.anual_pendente) botoes.push('<button data-nuvem-conferir="1">Já paguei o ano</button>');
  if (a.situacao === "authorized" && c.periodo !== "anual") botoes.push('<button class="perigo" data-nuvem-cancelar="1">Cancelar a assinatura</button>');
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
    ? '<p class="cfg-texto">O <b>PAULUS (nuvem)</b> escreve as respostas no modelo do plano do escritório: Llama 3.3 70B no Advogado, Mistral Large 3 no Escritório e Claude Sonnet 5.5 (com o Claude Opus 5.5 no nível Ministro) no Escritório Plus. ' +
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
    "o anexo guardado do e-mail (desta versão em diante), a cópia das pastas do Drive feita pelo PAULUS e o caso marcado só no escritório.</p>" +
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
  if (typeof entrarNoGoogleDoVinculo !== "function") { avisoCert("Vincule este PAULUS a uma conta Google antes (Configurações › Conta).", { tom: "erro" }); return; }
  let feito = false;
  try {
    await entrarNoGoogleDoVinculo("confirmar", async () => {
      const e = (typeof vinc !== "undefined" && vinc.estado) || {};
      if (feito || e.finalidade !== "confirmar") return;
      if (e.fase === "pronto") { feito = true; await tentar(); }
      else if (e.fase === "erro" || e.fase === "cancelado") { feito = true; avisoCert(e.mensagem || "não deu para entrar com o Google", { tom: "erro" }); }
    });
    avisoCert("Entre com o Google no navegador que abriu.");
  } catch (err) { avisoCert(err.message, { tom: "erro" }); }
}

async function recarregarNuvem(redesenhar, pacote) {
  // `pacote`: a recarga rapida de Plano e consumo ("0.5", "1", "2"); sem ele, a de sempre.
  const p = await nuvemPost("/api/nuvem/paulus/recarga", pacote ? { pacote: pacote } : {});
  if (!p) return;
  let parar = false;
  const html = '<div class="nuvem-pix">' + (p.qr_code_base64 ? '<img alt="QR do Pix" src="data:image/png;base64,' + esc(p.qr_code_base64) + '">' : "") +
    '<p>Pix de R$ ' + esc(String(p.valor).replace(".", ",")) + " · " + esc(tokens(p.tokens)) + " créditos · vale " + esc(String(p.vence_em_minutos)) + " min</p>" +
    '<textarea readonly class="nuvem-copia">' + esc(p.qr_code || "") + "</textarea>" +
    '<p class="nota" id="nuvem-pix-situacao">Esperando o pagamento…</p></div>';
  const olhar = async () => {
    while (!parar) {
      await new Promise((r) => setTimeout(r, 4000));
      if (parar) return;
      const r = await fetch("/api/nuvem/paulus/recarga/" + encodeURIComponent(p.id));
      if (!r.ok) continue;
      const s = await r.json();
      if (s.pago) {
        const el = document.getElementById("nuvem-pix-situacao");
        if (el) el.textContent = "Pago. Os créditos entraram.";
        parar = true;
        await carregarContaNuvem(true);
        redesenhar();
        return;
      }
    }
  };
  olhar();
  await dialogo({ titulo: "Recarga da nuvem", contexto: "Configurações › Modelos › Nuvem", classe: "dialogo-ver", confirmar: "Fechar", semCancelar: true, html });
  parar = true;
  await carregarContaNuvem(true);
  redesenhar();
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
    const r = await nuvemPost("/api/nuvem/paulus/plano", { plano: nuvemTela.plano });
    if (!r) return;
    nuvemTela.conta = r.conta || r;
    avisoCert(nuvemTela.conta.plano_proximo ? "Troca marcada: o plano novo vale a partir da renovação." : "Troca desfeita: o plano continua o de agora.");
    redesenhar();
  });
  raiz.querySelectorAll("[data-nuvem-assinar]").forEach((b) => { b.onclick = async () => {
    const anual = b.dataset.nuvemAssinar === "anual";
    const r = await nuvemPost("/api/nuvem/paulus/assinar", { plano: nuvemTela.plano, periodo: anual ? "anual" : "mensal" });
    if (!r) return;
    if (!r.link) { avisoCert("o Mercado Pago não devolveu a página da assinatura", { tom: "erro" }); return; }
    window.open(r.link, "_blank");
    avisoCert(anual ? "Pague o ano na página do Mercado Pago que abriu (em até 12 vezes); depois, “Já paguei o ano”."
      : "Ponha o cartão na página do Mercado Pago que abriu; depois, “Já pus o cartão”.");
    await carregarContaNuvem(true); redesenhar();
  }; });
  clique("[data-nuvem-conferir]", async () => {
    const r = await nuvemPost("/api/nuvem/paulus/assinatura", null, "GET");
    if (r) { nuvemTela.conta = r.conta; redesenhar(); }
  });
  clique("[data-nuvem-cancelar]", async () => {
    const res = await dialogo({ titulo: "Cancelar a assinatura?", texto: "Nada mais é cobrado. Os tokens do ciclo pago continuam valendo até o fim dele.",
      confirmar: "Cancelar a assinatura", cancelar: "Manter", perigo: true });
    if (!res || !res.ok) return;
    const r = await nuvemPost("/api/nuvem/paulus/cancelar", {});
    if (r) { nuvemTela.conta = r.conta; redesenhar(); }
  });
  clique("[data-nuvem-recarga]", () => recarregarNuvem(redesenhar));
  clique("[data-nuvem-sair]", async () => {
    const res = await dialogo({ titulo: "Desligar esta instalação?", texto: "O segredo desta instalação é apagado daqui e de paulus.ia.br. A conta e o plano continuam; para usar de novo, ative com o Google.",
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
