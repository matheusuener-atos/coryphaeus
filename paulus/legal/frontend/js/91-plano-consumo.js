/* ---------------------------------------------------- plano e consumo */
/*
   A central de consumo da IA (03/10/2026; desenho A24 · Assinatura v2, no
   visual da pasta de Servico): quanto o escritorio gasta, quem gasta, os
   limites e o plano. Nesta ordem - o consumo do ciclo no alto (o numero, a
   barra com a marca do dia e a ficha em faixa), depois um cartao para a
   equipe (com o historico de cada pessoa e o que se faz com ela), um para os
   limites e um para o plano (cobranca, pagamento, nota fiscal, pessoas e,
   so com o consumo alto, a recarga rapida). No cabecalho, o extrato do
   ciclo e os planos.

   O nome continua "Plano e consumo": "Assinatura" e a tela de assinar PDF.

   Os numeros do ciclo sao os do Worker (a conta que vale para a cobranca);
   quem gastou e em que sai do registro de envios deste computador
   (src/consumo.py). A equipe (titular, colaborador, convite) e a de
   Configuracoes › Acesso de fora (js/46-equipe.js). So na janela do
   escritorio: o historico mostra o comeco das perguntas de cada pessoa.
*/

const pc = { dados: null, aberto: null, historicos: {}, carregando: false };
const PC_ALERTA = 0.8;
const PC_RECARGA_A_PARTIR = 0.7;
const PC_RITMO_FOLGA = 0.1;
// A pagina do Mercado Pago onde quem paga troca o cartao da assinatura.
const PC_MP_ASSINATURAS = "https://www.mercadopago.com.br/subscriptions";
const PC_CONTATO = "contato@paulus.ia.br";
const PC_SITUACOES = { authorized: "ativa", pending: "esperando o cartão", paused: "pausada", cancelled: "cancelada" };

async function mostrarConsumo() {
  abrirTela("Plano e consumo", { cheia: true });
  marcarDestino("consumo");
  pc.aberto = null;
  $("conversa-meta").textContent = "Quanto o escritório usa da IA, quem usa, os limites e o plano";
  cascaConsumo('<p class="nota">lendo…</p>');
  await carregarConsumo(true);
}

async function carregarConsumo(forcar) {
  pc.carregando = true;
  try {
    const [r] = await Promise.all([fetch("/api/consumo" + (forcar ? "?forcar=true" : "")),
      typeof carregarAcessoDaEquipe === "function" ? carregarAcessoDaEquipe() : null]);
    pc.dados = r.ok ? await r.json() : null;
    if (!r.ok) pc.erro = await erroDe(r);
  } catch (err) {
    pc.dados = null;
    pc.erro = String(err.message || err);
  }
  pc.carregando = false;
  pc.historicos = {};
  if ($("pc-tela")) desenharConsumo();
}

function cascaConsumo(html) {
  $("centro").innerHTML = '<div class="acervo sem-painel pc-tela" id="pc-tela"><div class="acervo-principal sv-principal">' +
    '<div class="sv-medida">' + html + "</div></div></div>";
  atualizarPostura();
}

/* 1234 -> "1.234"; 120000 -> "120 mil"; 8400000 -> "8,4 mi". */
function tokCurto(n) {
  const v = Number(n) || 0;
  if (v >= 1e6) return (v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: v >= 1e8 ? 0 : 1 }) + " mi";
  if (v >= 1e4) return Math.round(v / 1e3).toLocaleString("pt-BR") + " mil";
  return v.toLocaleString("pt-BR");
}
function tokCheio(n) { return (Number(n) || 0).toLocaleString("pt-BR"); }
function pcData(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleDateString("pt-BR");
}
function reais(v) { return "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: Number(v) % 1 ? 2 : 0, maximumFractionDigits: 2 }); }
function pcPct(n) { return String(n).replace(".", ",") + "%"; }

/* O que a conta diz do ciclo: limite, usados, a parte usada e a parte do
   ciclo que ja passou (a marca do dia na barra). */
function cicloDe(c) {
  const ciclo = (c && c.ciclo) || {};
  const limite = Number(ciclo.tokens || ((c && c.plano) || {}).tokens || 0);
  const usados = Number(ciclo.usados || 0);
  const ini = Date.parse(ciclo.inicio || ""), fim = Date.parse(ciclo.fim || "");
  const decorrido = ini && fim && fim > ini ? Math.min(1, Math.max(0, (Date.now() - ini) / (fim - ini))) : null;
  return { limite, usados, parte: limite ? Math.min(1, usados / limite) : 0, decorrido, fim: ciclo.fim || "" };
}

function cabecalhoConsumo() {
  const c = pc.dados && pc.dados.conta;
  $("acoes-tela").innerHTML =
    '<button class="com-icone" data-pc-extrato="1">' + ic("receipt_long", 16) + "Extrato do ciclo</button>" +
    (c && !c.cortesia && (c.planos || []).length ? '<button class="com-icone" data-pc-upgrade="1">' + ic("arrow_upward", 16) + "Ver planos</button>" : "");
}

function desenharConsumo() {
  const d = pc.dados;
  if (!d) {
    cascaConsumo('<p class="pc-vazio">Não consegui ler o consumo: ' + esc(pc.erro || "o servidor não respondeu") + ".</p>");
    return;
  }
  const c = d.conta;
  cabecalhoConsumo();
  cascaConsumo(blocoGeral(d, c) + blocoEquipe(d) + blocoLimites(d) + blocoPlano(d, c));
  ligarConsumo();
}

/* ------------------------------------------------- 1. o consumo do ciclo */

function blocoGeral(d, c) {
  if (!c) {
    const motivo = d.erro
      ? "Sem conseguir falar com paulus.ia.br agora (" + esc(d.erro) + "): os números do plano voltam quando a internet voltar."
      : "A conta da IA ainda não está ligada neste PAULUS. Ligue com a conta Google em Configurações › Modelos, ou assine em paulus.ia.br/cadastro.";
    return '<header class="pc-geral"><span class="pc-rotulo">Consumo do ciclo</span><p class="pc-texto">' + motivo + "</p>" +
      '<div class="linha-form"><button class="primario" data-pc-ir="modelos">Abrir Configurações › Modelos</button></div></header>';
  }
  const t = c.tokens || {};
  const k = cicloDe(c);
  const pct = Math.round(k.parte * 100);
  const classe = k.parte >= 0.9 ? " esgotado" : k.parte >= PC_RECARGA_A_PARTIR ? " alto" : "";
  const plano = c.cortesia ? "Cortesia" : (c.plano || {}).nome || "Plano";
  const ativa = (c.assinatura || {}).situacao === "authorized";
  const renova = c.plano_vigente && k.fim ? (ativa ? "renova em " : "vale até ") + pcData(k.fim) : "sem plano em dia";
  // O ritmo: a parte usada contra a parte do ciclo que ja passou.
  let ritmo = '<b class="pc-apagado">—</b>';
  if (c.plano_vigente && k.decorrido !== null && k.limite) {
    ritmo = k.parte > k.decorrido + PC_RITMO_FOLGA ? '<b class="pc-valor-alto">acima do esperado</b>' : '<b class="pc-valor-ok">dentro do esperado</b>';
  }
  const marca = k.decorrido !== null && c.plano_vigente
    ? '<span class="pc-marca" style="left:' + (k.decorrido * 100).toFixed(1) + '%" title="hoje: ' + Math.round(k.decorrido * 100) + '% do ciclo"></span>' : "";
  const item = (rotulo, valor) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rotulo + "</span>" + valor + "</div>";
  const alertas = (d.painel.alertas || []).map((a) => '<p class="pc-alerta-linha">' + ic("error", 16) + esc(a) + "</p>").join("") +
    (c.plano_vigente ? "" : '<p class="pc-alerta-linha">' + ic("error", 16) + "Sem o plano em dia, o PAULUS funciona sem IA.</p>");
  return '<header class="pc-geral' + classe + '" aria-labelledby="pc-t-geral">' +
    '<div class="pc-geral-topo"><span class="pc-rotulo" id="pc-t-geral">Consumo do ciclo</span>' +
    '<span class="pc-chip">' + esc(plano) + " · " + esc(renova) + "</span></div>" +
    '<div class="pc-numeros"><div class="pc-grande"><b>' + esc(tokCurto(k.usados)) + "</b><span>de " + esc(tokCurto(k.limite)) +
    " tokens do plano usados</span></div>" + '<span class="pc-pct">' + pct + "%</span></div>" +
    '<div class="pc-barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + pct + '" aria-label="Uso do ciclo">' +
    '<div class="pc-barra-trilho"><i style="width:' + pct + '%"></i></div>' + marca + "</div>" +
    '<div class="sv-ficha pc-ficha">' +
    item("Restantes", "<b>" + esc(tokCurto(t.restantes || 0)) + "</b>") +
    item("Hoje", "<b>" + esc(tokCurto(t.hoje || 0)) + "</b>") +
    item("Da recarga", "<b>" + esc(tokCurto(t.da_recarga || 0)) + "</b>") +
    item("Ritmo", ritmo) + "</div>" + alertas + "</header>";
}

/* --------------------------------------------- 2. quem esta consumindo */

/* A conta de acesso (Configuracoes › Acesso de fora) de quem aparece no
   consumo: o id e o mesmo. 0 e a janela do escritorio, sem conta. */
function contaDaPessoa(id) {
  return typeof eqp !== "undefined" ? (eqp.contas || []).find((c) => Number(c.id) === Number(id)) : null;
}

function papelNoConsumo(x) {
  if (x.conta_id === 0) return "janela do escritório";
  if (x.conta_id < 0) return "registro antigo";
  const conta = contaDaPessoa(x.conta_id);
  if (!conta) return "sem acesso agora";
  return conta.papel === "titular" ? "titular" : (conta.pronta ? "colaborador" : "colaborador · falta o autenticador");
}

function textoDoLimite(x) {
  const l = x.limite;
  if (!l) return { texto: "sem limite próprio", alto: false };
  if (x.alerta) return { texto: x.alerta, alto: true };
  const partes = [];
  if (l.mensal) partes.push(Math.round((100 * x.tokens) / l.mensal) + "% do limite de " + tokCurto(l.mensal) + " no ciclo");
  if (l.diario) partes.push(Math.round((100 * (x.hoje || 0)) / l.diario) + "% do diário de " + tokCurto(l.diario));
  return { texto: partes.join(" · "), alto: false };
}

function blocoEquipe(d) {
  const p = d.painel;
  const pessoas = (p.pessoas || []).filter((x) => x.tokens > 0 || x.limite || x.conta_id > 0);
  const maior = Math.max(1, ...pessoas.map((x) => x.tokens));
  const linhas = pessoas.map((x) => {
    const aberto = pc.aberto === x.conta_id;
    const largura = Math.max(x.tokens ? 2 : 0, Math.round((100 * x.tokens) / maior));
    const lim = textoDoLimite(x);
    return '<div class="pc-pessoa' + (aberto ? " aberta" : "") + '">' +
      '<button type="button" class="pc-pessoa-linha" data-pc-pessoa="' + x.conta_id + '" aria-expanded="' + aberto + '">' +
      '<span class="cad-avatar">' + esc(iniciaisDoRemetente(x.nome)) + "</span>" +
      '<span class="duas-linhas pc-quem"><b class="corta">' + esc(x.nome) + '</b><small class="corta">' + esc(papelNoConsumo(x)) + "</small></span>" +
      '<span class="pc-medida"><span class="pc-trilho"><i style="width:' + largura + '%"></i></span>' +
      '<small class="pc-limite-txt' + (lim.alto ? " alto" : "") + (/atingiu/.test(x.alerta || "") ? " no-limite" : "") + '">' +
      (lim.alto ? '<span class="pc-ponto"></span>' : "") + esc(lim.texto) + "</small></span>" +
      '<span class="pc-qtd"><b>' + esc(tokCurto(x.tokens)) + "</b> · " + esc(pcPct(x.porcento)) + "</span>" +
      ic("expand_more", 18) + "</button>" +
      (aberto ? '<div class="pc-historico">' + historicoDe(x.conta_id) + acoesDaPessoa(x) + "</div>" : "") + "</div>";
  }).join("");
  // Os convites em aberto: a pessoa ainda nao entrou, entao nao gastou.
  const convites = (typeof eqp !== "undefined" ? eqp.convites || [] : []).filter((v) => v.estado === "aberto").map((v) =>
    '<div class="pc-pessoa pc-convite"><span class="pc-pessoa-linha"><span class="cad-avatar">' + esc(iniciaisDoRemetente(v.nome || v.email)) + "</span>" +
    '<span class="duas-linhas pc-quem"><b class="corta">' + esc(v.nome || v.email) + '</b><small class="corta">convite enviado · ' + esc(v.email) + "</small></span>" +
    '<span class="pc-medida"><small class="pc-limite-txt">espera a pessoa abrir o link</small></span><span class="pc-qtd">—</span><span></span></span></div>').join("");
  const total = pessoas.length;
  return '<section class="sv-secao pc-secao" aria-labelledby="pc-t-equipe"><div class="sv-secao-cabeca">' +
    '<span class="sv-secao-titulo" id="pc-t-equipe">' + ic("group", 16) + "Quem está consumindo</span>" +
    '<span class="sv-secao-meta">neste ciclo · ' + esc(tokCurto(p.total)) + " tokens · " + plural(total, "pessoa") + "</span>" +
    '<button type="button" class="sv-ligacao" data-pc-convidar="1">' + ic("person_add", 15) + "Convidar pessoa</button></div>" +
    (linhas || convites ? '<div class="pc-equipe">' + linhas + convites + "</div>" : '<p class="sv-dica">Nenhum envio à nuvem neste ciclo ainda.</p>') +
    '<p class="sv-dica">Clique num nome para ver o histórico. Quem gastou sai do registro de envios deste computador; o total que vale para o plano é o de paulus.ia.br.</p></section>';
}

function historicoDe(id) {
  const h = pc.historicos[id];
  if (!h) return '<p class="nota">lendo…</p>';
  if (!h.length) return '<p class="pc-texto">Sem envios nos últimos 31 dias.</p>';
  return h.map((dia) => '<div class="pc-dia"><div class="pc-dia-cabeca"><b>' + esc(dia.rotulo) + "</b><span>" + esc(tokCurto(dia.tokens)) + " tokens</span></div>" +
    dia.itens.map((i) => {
      const hora = String(i.quando).slice(11, 16);
      const texto = '<span class="pc-hora">' + esc(hora) + '</span><span class="pc-pergunta">“' + esc(i.pergunta || "sem texto") + '”</span>' +
        '<span class="pc-tok">' + esc(tokCheio(i.tokens)) + "</span>";
      return i.trabalho_id
        ? '<button type="button" class="pc-item" data-pc-conversa="' + esc(i.trabalho_id) + '" title="Abrir a conversa">' + texto + "</button>"
        : '<div class="pc-item">' + texto + "</div>";
    }).join("") + "</div>").join("");
}

/* O que se faz com a pessoa, embaixo do historico: o limite, e - para quem
   tem conta - as permissoes, o papel e tirar o acesso. */
function acoesDaPessoa(x) {
  const acoes = ['<button type="button" class="sv-ligacao" data-pc-limites="1">' + (x.limite ? "Ajustar limite" : "Definir limite") + "</button>"];
  const conta = x.conta_id > 0 ? contaDaPessoa(x.conta_id) : null;
  if (conta) {
    if (conta.papel !== "titular") acoes.push('<button type="button" class="sv-ligacao" data-pc-permissoes="' + conta.id + '">Permissões</button>');
    acoes.push('<button type="button" class="sv-ligacao" data-pc-papel="' + conta.id + '">' + (conta.papel === "titular" ? "Deixar de ser titular" : "Tornar titular") + "</button>");
    acoes.push('<button type="button" class="sv-ligacao acc pc-remover" data-pc-remover="' + conta.id + '">Tirar o acesso</button>');
  }
  return '<div class="pc-pessoa-acoes">' + acoes.join("") + "</div>";
}

async function abrirHistorico(id) {
  pc.aberto = pc.aberto === id ? null : id;
  desenharConsumo();
  if (pc.aberto === null || pc.historicos[id]) return;
  try {
    const r = await fetch("/api/consumo/pessoa/" + encodeURIComponent(id));
    pc.historicos[id] = r.ok ? (await r.json()).dias || [] : [];
  } catch (err) {
    pc.historicos[id] = [];
  }
  if ($("pc-tela") && pc.aberto === id) desenharConsumo();
}

/* Titular cuida das contas e pode tudo, tambem de fora; o colaborador segue
   as permissoes. Mudar o papel derruba a sessao da pessoa (src/acesso/contas.py). */
async function mudarPapel(id) {
  const conta = contaDaPessoa(id);
  if (!conta) return;
  const titular = conta.papel === "titular";
  const ok = await confirmar({
    titulo: titular ? "Deixar " + conta.nome + " como colaborador?" : "Tornar " + conta.nome + " titular?", contexto: "Plano e consumo",
    texto: (titular ? "Passa a seguir as permissões de colaborador." : "O titular cuida das contas e pode tudo, também de fora — inclusive o Financeiro e o plano.") +
      "\nSe estiver dentro agora, entra de novo, já com o papel novo.",
    confirmar: titular ? "Deixar como colaborador" : "Tornar titular" });
  if (!ok) return;
  try {
    await acessoPost("/api/acesso/contas/" + conta.id, { papel: titular ? "colaborador" : "titular" }, "PATCH");
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return; }
  avisoCert(conta.nome.split(" ")[0] + (titular ? " agora é colaborador." : " agora é titular."));
  await carregarConsumo(false);
}

async function tirarAcesso(id) {
  const conta = contaDaPessoa(id);
  if (!conta) return;
  const ok = await confirmar({
    titulo: "Tirar o acesso de " + conta.nome + "?", contexto: "Plano e consumo",
    texto: "A conta deixa de entrar no PAULUS, e quem estiver dentro sai agora. O que a pessoa fez fica, e o consumo dela no histórico também.\nPara voltar, é só convidar de novo.",
    confirmar: "Tirar o acesso", perigo: true });
  if (!ok) return;
  try {
    await acessoPost("/api/acesso/contas/" + conta.id, undefined, "DELETE");
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return; }
  pc.aberto = null;
  avisoCert(conta.nome + " não tem mais acesso; o histórico fica guardado.");
  await carregarConsumo(false);
}

/* ------------------------------------------------------ 3. os limites */

function blocoLimites(d) {
  const l = d.painel.limites || {};
  const pessoas = d.painel.pessoas || [];
  const linha = (nome, teto, gasto, quando) => {
    const parte = teto ? gasto / teto : 0;
    const classe = parte >= 1 ? " no-limite" : parte >= PC_ALERTA ? " alto" : "";
    return '<div class="pc-limite-item' + classe + '"><span class="corta">' + esc(nome) + "</span>" +
      '<span class="pc-limite-qual">' + esc(quando) + "</span>" +
      '<span class="pc-limite-uso">' + (parte >= PC_ALERTA ? '<span class="pc-ponto"></span>' : "") + esc(tokCurto(gasto)) + " de " + esc(tokCurto(teto)) +
      " · " + Math.round(parte * 100) + "%</span></div>";
  };
  const itens = [];
  if (l.diario) itens.push(linha("O escritório inteiro", l.diario, d.painel.hoje || 0, "por dia"));
  if (l.mensal) itens.push(linha("O escritório inteiro", l.mensal, d.painel.total || 0, "no ciclo"));
  Object.keys(l.pessoas || {}).forEach((k) => {
    const x = pessoas.find((p) => String(p.conta_id) === k) || { nome: "Pessoa da equipe", tokens: 0, hoje: 0 };
    const lp = l.pessoas[k];
    if (lp.diario) itens.push(linha(x.nome, lp.diario, x.hoje || 0, "por dia"));
    if (lp.mensal) itens.push(linha(x.nome, lp.mensal, x.tokens || 0, "no ciclo"));
  });
  const perto = pessoas.filter((x) => x.alerta).map((x) => x.nome.split(" ")[0]);
  const meta = perto.length ? perto.join(" e ") + (perto.length > 1 ? " estão" : " está") + " perto do limite"
    : itens.length ? plural(itens.length, "limite") : "sem limites";
  return '<section class="sv-secao pc-secao" aria-labelledby="pc-t-limites"><div class="sv-secao-cabeca">' +
    '<span class="sv-secao-titulo" id="pc-t-limites">' + ic("tune", 16) + "Limites de uso</span>" +
    '<span class="sv-secao-meta' + (perto.length ? " pc-valor-alto" : "") + '">' + esc(meta) + "</span>" +
    '<button type="button" class="sv-ligacao" data-pc-limites="1">' + ic("edit", 15) + "Ajustar limites</button></div>" +
    (itens.length ? '<div class="pc-limites-lista">' + itens.join("") + "</div>" : '<p class="sv-dica pc-sem">Sem limites: a equipe usa até o fim dos tokens do plano.</p>') +
    '<p class="sv-dica">Passado um limite, a pergunta é escrita pelo modelo deste computador, e a resposta diz por quê. A tela avisa a partir de 80%.</p></section>';
}

async function ajustarLimites() {
  const d = pc.dados;
  const l = d.painel.limites || {};
  const pessoas = d.painel.pessoas || [];
  const campo = (chave, valor, rotulo) => '<label class="pc-campo"><span>' + esc(rotulo) + "</span>" +
    '<input type="text" inputmode="numeric" data-dialogo-chave="' + chave + '" value="' + esc(valor ? tokCheio(valor) : "") + '" placeholder="sem limite"></label>';
  const html = '<div class="pc-limites">' +
    '<p class="pc-texto">Tokens por dia e por ciclo. Em branco, sem limite. Passado o limite, a pergunta é escrita pelo modelo deste computador, e a resposta diz por quê.</p>' +
    '<span class="sv-kicker">Escritório</span>' +
    '<div class="pc-limite-linha"><span class="duas-linhas"><b>O escritório inteiro</b><small>usou ' + esc(tokCurto(d.painel.total || 0)) + " no ciclo</small></span>" +
    campo("diario", l.diario, "Diário") + campo("mensal", l.mensal, "No ciclo") + "</div>" +
    '<span class="sv-kicker">Por pessoa</span>' +
    pessoas.filter((x) => x.conta_id >= 0).map((x) => {
      const p = (l.pessoas || {})[String(x.conta_id)] || {};
      return '<div class="pc-limite-linha"><span class="duas-linhas"><b class="corta">' + esc(x.nome) + "</b><small" + (x.alerta ? ' class="pc-valor-alto"' : "") + ">usou " +
        esc(tokCurto(x.tokens)) + " no ciclo</small></span>" + campo("p:" + x.conta_id + ":diario", p.diario, "Diário") +
        campo("p:" + x.conta_id + ":mensal", p.mensal, "No ciclo") + "</div>";
    }).join("") + "</div>";
  const r = await dialogo({ titulo: "Limites de uso", contexto: "Plano e consumo", html: html, confirmar: "Salvar limites", classe: "pc-dialogo" });
  if (!r || !r.ok) return;
  const v = r.valores || {};
  const numero = (t) => Number(String(t || "").replace(/\D/g, "")) || 0;
  const corpo = { diario: numero(v.diario), mensal: numero(v.mensal), pessoas: {} };
  Object.keys(v).forEach((k) => {
    const m = k.match(/^p:(-?\d+):(diario|mensal)$/);
    if (!m) return;
    corpo.pessoas[m[1]] = corpo.pessoas[m[1]] || {};
    corpo.pessoas[m[1]][m[2]] = numero(v[k]);
  });
  const res = await fetch("/api/consumo/limites", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  if (!res.ok) { avisoCert(await erroDe(res), { tom: "erro" }); return; }
  const novo = await res.json();
  pc.dados.painel = novo.painel;
  avisoCert("Limites salvos.");
  desenharConsumo();
}

/* ------------------------------------------------- 4. o plano */

function blocoPlano(d, c) {
  if (!c) return "";
  const plano = c.plano || {};
  const a = c.assinatura || null;
  const ativa = (a || {}).situacao === "authorized";
  const k = cicloDe(c);
  const linha = c.cortesia ? "Cortesia · " + tokCurto(plano.tokens) + " tokens por ciclo"
    : plano.nome + " · " + tokCurto(plano.tokens) + " tokens por mês · " + reais(plano.valor) + "/mês";
  const item = (rotulo, valor, acao) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rotulo + "</span><b class=\"corta\">" + esc(valor) + "</b>" + (acao || "") + "</div>";
  const ligacao = (dado, rotulo) => '<button type="button" class="pc-sublinhado" ' + dado + ">" + esc(rotulo) + "</button>";
  const proximo = c.plano_proximo || plano;
  let cobranca, pagamento;
  if (c.cortesia) {
    cobranca = item("Próxima cobrança", "nenhuma · cortesia", "");
    pagamento = item("Pagamento", "sem cartão", "");
  } else if (ativa) {
    cobranca = item("Próxima cobrança", (k.fim ? pcData(k.fim) + " · " : "") + reais(proximo.valor), ligacao('data-pc-pagamentos="1"', "Ver pagamentos"));
    pagamento = item("Pagamento", "Mercado Pago · " + PC_SITUACOES.authorized, ligacao('data-pc-cartao="1"', "Alterar cartão"));
  } else if (a) {
    cobranca = item("Próxima cobrança", a.situacao === "cancelled" ? "nenhuma" : "quando o cartão entrar",
      ligacao('data-pc-pagamentos="1"', "Ver pagamentos"));
    pagamento = item("Pagamento", "Mercado Pago · " + (PC_SITUACOES[a.situacao] || a.situacao),
      a.situacao === "cancelled" ? ligacao('data-pc-upgrade="1"', "Assinar de novo") : ligacao('data-pc-cartao="1"', "Abrir no Mercado Pago"));
  } else {
    cobranca = item("Próxima cobrança", "sem assinatura", ligacao('data-pc-upgrade="1"', "Assinar"));
    pagamento = item("Pagamento", "sem cartão", "");
  }
  const contas = typeof eqp !== "undefined" ? (eqp.contas || []).length : 0;
  const convites = typeof eqp !== "undefined" ? (eqp.convites || []).filter((v) => v.estado === "aberto").length : 0;
  const ficha = '<div class="sv-ficha pc-ficha pc-ficha-plano">' + cobranca + pagamento +
    item("Nota fiscal", "ainda não sai sozinha", ligacao('data-pc-nota="1"', "Pedir por e-mail")) +
    item("Pessoas", plural(contas, "conta") + " com acesso" + (convites ? " · " + plural(convites, "convite") : ""), ligacao('data-pc-convidar="1"', "Convidar")) + "</div>";
  const troca = c.plano_proximo ? '<p class="sv-dica pc-troca">' + ic("schedule", 15) + "A partir da renovação: " + esc(c.plano_proximo.nome) + " (" +
    esc(tokCurto(c.plano_proximo.tokens)) + " tokens, " + esc(reais(c.plano_proximo.valor)) + "/mês).</p>" : "";
  const rodape = ativa
    ? '<p class="sv-dica">Ao cancelar, nada mais é cobrado e os tokens do ciclo pago valem até ' + esc(pcData(k.fim) || "o fim dele") + ". " +
      '<button type="button" class="pc-sublinhado" data-pc-cancelar="1">Cancelar assinatura</button></p>'
    : '<p class="sv-dica">Os planos têm os mesmos recursos e servem à equipe inteira; o que muda é a quantidade de tokens.</p>';
  return '<section class="sv-secao pc-secao" aria-labelledby="pc-t-plano"><div class="sv-secao-cabeca">' +
    '<span class="sv-secao-titulo" id="pc-t-plano">' + ic("workspace_premium", 16) + "Seu plano</span>" +
    '<span class="sv-secao-meta">' + esc(linha) + "</span>" +
    (c.cortesia ? "" : '<button type="button" class="sv-ligacao" data-pc-upgrade="1">' + ic("arrow_upward", 15) + "Ver planos</button>") + "</div>" +
    '<div class="pc-plano-miolo">' + ficha + troca + blocoRecarga(c) + "</div>" + rodape + "</section>";
}

async function verUpgrade() {
  const c = pc.dados.conta || {};
  const atual = (c.plano || {}).id;
  const marcado = (c.plano_proximo || c.plano || {}).id;
  const planos = c.planos || [];
  const ativa = (c.assinatura || {}).situacao === "authorized";
  const tokensAtual = Number((c.plano || {}).tokens || 0);
  const colunas = planos.map((p) => {
    const eAtual = p.id === atual;
    const eMarcado = p.id === marcado && p.id !== atual;
    const perguntas = Math.round(p.tokens / 3500 / 100) * 100;
    let rotulo, desliga = false;
    if (!ativa) rotulo = "Assinar o " + p.nome;
    else if (eAtual) { rotulo = c.plano_proximo ? "Ficar no " + p.nome : "Plano atual"; desliga = !c.plano_proximo; }
    else if (eMarcado) { rotulo = "Troca marcada"; desliga = true; }
    else rotulo = (p.tokens > tokensAtual ? "Mudar para o " : "Reduzir para o ") + p.nome;
    return '<div class="pc-plano-col' + (eAtual ? " atual" : "") + '">' +
      '<div class="pc-plano-nome"><span>' + esc(p.nome) + "</span>" + (eAtual ? '<em class="sv-kicker">atual</em>' : eMarcado ? '<em class="sv-kicker">na renovação</em>' : "") + "</div>" +
      '<div class="pc-plano-tok"><b>' + esc(tokCurto(p.tokens)) + "</b><small>tokens por mês · " + esc(reais(p.valor)) + "/mês</small></div>" +
      '<ul class="pc-plano-itens"><li>~' + esc(perguntas.toLocaleString("pt-BR")) + " perguntas por mês</li>" +
      "<li>" + esc(reais(Math.round((p.valor / p.tokens) * 1e6 * 100) / 100)) + " por milhão de tokens</li>" +
      "<li>A equipe inteira, com limites por pessoa</li><li>Recarga em pacotes quando faltar</li></ul>" +
      '<button type="button" class="' + (!desliga && p.tokens > tokensAtual ? "primario" : "") + '" data-pc-opcao="' + esc(p.id) + '"' + (desliga ? " disabled" : "") + ">" + esc(rotulo) + "</button></div>";
  }).join("");
  let escolhido = "";
  const aberto = dialogo({
    titulo: "Planos", contexto: "Plano e consumo", classe: "pc-dialogo pc-dialogo-planos", confirmar: "Fechar", semCancelar: true,
    html: '<p class="pc-texto">' + (ativa ? "Trocar vale na próxima renovação: o valor novo é cobrado nela, e os tokens do plano novo entram com ela. Tokens não usados não passam para o ciclo seguinte."
      : "A assinatura abre no Mercado Pago, onde se põe o cartão.") + "</p>" + '<div class="pc-planos">' + colunas + "</div>" });
  document.querySelectorAll("#veu-dialogo [data-pc-opcao]").forEach((b) => b.addEventListener("click", () => {
    escolhido = b.dataset.pcOpcao;
    if (dialogoAberto) dialogoAberto.fechar(null);
  }));
  await aberto;
  if (!escolhido) return;
  if (ativa) {
    if (escolhido === marcado) return;
    const res = await nuvemPost("/api/nuvem/paulus/plano", { plano: escolhido });
    if (!res) return;
    avisoCert((res.conta || {}).plano_proximo ? "Troca marcada: o plano novo vale a partir da renovação." : "Troca desfeita: o plano continua o de agora.");
  } else {
    const res = await nuvemPost("/api/nuvem/paulus/assinar", { plano: escolhido });
    if (!res) return;
    if (res.link) window.open(res.link, "_blank");
    avisoCert("Ponha o cartão na página do Mercado Pago que abriu.");
  }
  await carregarConsumo(true);
}

/* A mensalidade e as recargas pagas (as dez ultimas, do Worker). */
async function verPagamentos() {
  const c = pc.dados.conta || {};
  const a = c.assinatura || {};
  const linhas = [];
  if (a.id) {
    linhas.push('<div class="pc-pag-linha"><span class="duas-linhas"><b>Assinatura · ' + esc((c.plano || {}).nome || "") + "</b><small>" +
      esc((a.desde ? "desde " + pcData(a.desde) + " · " : "") + (PC_SITUACOES[a.situacao] || a.situacao || "")) + "</small></span>" +
      "<b>" + esc(reais(a.valor || (c.plano || {}).valor || 0)) + "/mês</b></div>");
  }
  (c.recargas || []).forEach((r) => linhas.push('<div class="pc-pag-linha"><span class="duas-linhas"><b>Recarga · +' + esc(tokCurto(r.tokens)) + " tokens</b><small>" +
    esc(pcData(r.quando)) + " · Pix</small></span><b>" + esc(reais(r.valor)) + "</b></div>"));
  await dialogo({ titulo: "Pagamentos", contexto: "Plano e consumo", classe: "pc-dialogo", confirmar: "Fechar", semCancelar: true,
    html: (linhas.length ? '<div class="pc-pag">' + linhas.join("") + "</div>" : '<p class="pc-texto">Nenhum pagamento ainda.</p>') +
      '<p class="pc-texto">As cobranças da mensalidade e os recibos ficam na sua conta do Mercado Pago, no e-mail de quem paga.</p>' });
}

async function pedirNotaFiscal() {
  const c = pc.dados.conta || {};
  if (typeof telaEscrever !== "function") { window.open("mailto:" + PC_CONTATO); return; }
  marcarDestino("caixa");
  await telaEscrever({ para: PC_CONTATO, assunto: "Nota fiscal da assinatura do PAULUS",
    corpo: "Olá! Peço a nota fiscal da assinatura do PAULUS (plano " + ((c.plano || {}).nome || "") + ", conta " + (c.email || "") + ").\n\n" +
      "Os dados para a nota (CPF ou CNPJ) são os do cadastro em paulus.ia.br/cadastro.\n\nObrigado." });
}

async function cancelarAssinatura() {
  const k = cicloDe(pc.dados.conta);
  const ok = await confirmar({ titulo: "Cancelar a assinatura?", contexto: "Plano e consumo",
    texto: "Nada mais é cobrado. Os tokens do ciclo pago continuam valendo até " + (pcData(k.fim) || "o fim dele") + "; depois, o PAULUS segue sem IA. Os seus documentos e conversas ficam neste computador.",
    confirmar: "Cancelar a assinatura", cancelar: "Manter", perigo: true });
  if (!ok) return;
  const r = await nuvemPost("/api/nuvem/paulus/cancelar", {});
  if (!r) return;
  avisoCert("Assinatura cancelada: nada mais é cobrado.");
  await carregarConsumo(true);
}

/* ------------------------------------------------ 5. a recarga rapida */

function blocoRecarga(c) {
  if (!c || !c.plano_vigente || c.cortesia) return "";
  const k = cicloDe(c);
  if (!k.limite || k.usados / k.limite < PC_RECARGA_A_PARTIR) return "";
  const pacotes = c.recargas_pacotes || [];
  if (!pacotes.length) return "";
  const dias = k.fim ? Math.max(0, Math.ceil((Date.parse(k.fim) - Date.now()) / 864e5)) : 0;
  return '<div class="pc-recarga"><p class="pc-texto"><b>Precisando de mais tokens neste ciclo?</b> Você já usou ' + Math.round(k.parte * 100) + "%" +
    (dias ? " com " + plural(dias, "dia") + " pela frente" : "") + ". A recarga entra na hora, no Pix, e não vence na renovação.</p>" +
    '<div class="pc-acoes">' + pacotes.map((p) => '<button data-pc-recarga="' + esc(p.id) + '">+' + esc(tokCurto(p.tokens)) +
      ' <span class="pc-preco">· ' + esc(reais(p.valor)) + "</span></button>").join("") + "</div></div>";
}

/* ------------------------------------------------------- 6. o extrato */

async function verExtrato() {
  let e;
  try {
    const r = await fetch("/api/consumo/extrato");
    if (!r.ok) throw new Error(await erroDe(r));
    e = await r.json();
  } catch (err) { avisoCert("Não consegui ler o extrato: " + err.message, { tom: "erro" }); return; }
  const lista = (itens) => itens.length ? itens.map((x) => '<div class="pc-extrato-linha"><span class="corta" title="' + esc(x.nome) + '">' + esc(x.nome) + "</span>" +
    '<span class="pc-extrato-pct">' + esc(pcPct(x.porcento)) + "</span><b>" + esc(tokCurto(x.tokens)) + "</b></div>").join("")
    : '<p class="pc-texto">Nenhum envio à nuvem neste ciclo.</p>';
  const ini = (e.ciclo || {}).inicio, fim = (e.ciclo || {}).fim;
  const periodo = (ini ? pcData(ini) : "") + (fim ? " a " + pcData(fim) : " até hoje");
  const html = '<div class="pc-extrato"><div><span class="sv-kicker">Por área</span>' + lista(e.areas || []) + "</div>" +
    '<div><span class="sv-kicker">Por pessoa</span>' + lista(e.pessoas || []) + "</div></div>" +
    '<p class="pc-texto pc-extrato-total">Total <b>' + esc(tokCheio(e.total)) + " tokens</b>" +
    (e.custo !== null && e.custo !== undefined ? " · pela conta do plano, <b>" + esc(reais(e.custo)) + "</b> (" + esc(reais(e.por_milhao)) + " por milhão)" : "") + ".</p>" +
    '<p class="sv-dica">O custo é a parte do valor do plano que esses tokens representam, não uma cobrança à parte. O PDF fica no Acervo, em Relatórios › Consumo da IA.</p>';
  const r = await dialogo({ titulo: "Extrato do ciclo", contexto: periodo + (e.plano ? " · plano " + e.plano : ""), html: html, classe: "pc-dialogo",
    confirmar: "Enviar por e-mail", segundo: { rotulo: "Baixar PDF" }, cancelar: "Fechar" });
  if (!r || !r.ok) return;
  const pdf = await gerarPdfDoExtrato();
  if (!pdf) return;
  if (r.segundo) {
    const a = document.createElement("a");
    a.href = "/api/consumo/extrato/arquivo?nome=" + encodeURIComponent(pdf.nome);
    a.download = pdf.nome;
    document.body.appendChild(a);
    a.click();
    a.remove();
    avisoCert(pdf.nome + " baixado — e guardado no Acervo, em Relatórios › Consumo da IA.");
    return;
  }
  marcarDestino("caixa");
  await telaEscrever({ para: "", assunto: "Extrato de consumo da IA · " + periodo,
    corpo: "Segue o extrato de consumo da IA do ciclo " + periodo + ": " + tokCheio(e.total) + " tokens" +
      (e.custo !== null && e.custo !== undefined ? ", " + reais(e.custo) + " pela conta do plano" : "") + ".\n\nO detalhe por área e por pessoa vai no PDF anexo.",
    anexos: [pdf] });
  avisoCert("E-mail pronto para revisar — enviar passa por Aprovações conforme o seu limite", { tom: "ok" });
}

async function gerarPdfDoExtrato() {
  try {
    const r = await fetch("/api/consumo/extrato/pdf", { method: "POST" });
    if (!r.ok) throw new Error(await erroDe(r));
    return await r.json();
  } catch (err) { avisoCert(err.message, { tom: "erro" }); return null; }
}

/* -------------------------------------------------------------- cliques */

function ligarConsumo() {
  const tela = $("pc-tela");
  if (!tela) return;
  const clique = (sel, fn) => document.querySelectorAll("#pc-tela " + sel + ", #acoes-tela " + sel).forEach((b) => { b.onclick = (ev) => { ev.stopPropagation(); fn(b); }; });
  clique("[data-pc-pessoa]", (b) => abrirHistorico(Number(b.dataset.pcPessoa)));
  clique("[data-pc-conversa]", async (b) => { marcarDestino("conversa"); if (!(await abrirTrabalho(b.dataset.pcConversa))) avisoCert("Essa conversa não existe mais."); });
  clique("[data-pc-ir]", (b) => { marcarDestino("config"); mostrarConfig(b.dataset.pcIr); });
  clique("[data-pc-limites]", ajustarLimites);
  clique("[data-pc-upgrade]", verUpgrade);
  clique("[data-pc-extrato]", verExtrato);
  clique("[data-pc-pagamentos]", verPagamentos);
  clique("[data-pc-cartao]", () => window.open(PC_MP_ASSINATURAS, "_blank"));
  clique("[data-pc-nota]", pedirNotaFiscal);
  clique("[data-pc-cancelar]", cancelarAssinatura);
  clique("[data-pc-convidar]", () => convidarDaEquipe(() => carregarConsumo(false)));
  clique("[data-pc-papel]", (b) => mudarPapel(Number(b.dataset.pcPapel)));
  clique("[data-pc-remover]", (b) => tirarAcesso(Number(b.dataset.pcRemover)));
  clique("[data-pc-permissoes]", async (b) => {
    const conta = contaDaPessoa(Number(b.dataset.pcPermissoes));
    if (conta && typeof acessoPermissoes === "function") await acessoPermissoes(conta);
    await carregarConsumo(false);
  });
  clique("[data-pc-recarga]", (b) => recarregarNuvem(() => carregarConsumo(true), b.dataset.pcRecarga));
}
