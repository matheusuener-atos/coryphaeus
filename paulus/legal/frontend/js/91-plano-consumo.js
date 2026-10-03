/* ---------------------------------------------------- plano e consumo */
/*
   A central de consumo da IA (03/10/2026): quanto o escritorio gasta, quem
   gasta, e se e preciso limitar ou aumentar. Nesta ordem - consumo do ciclo,
   a equipe (com o historico de cada pessoa), os limites, o plano e, so com o
   consumo alto, a recarga rapida.

   Os numeros do ciclo sao os do Worker (a conta que vale para a cobranca);
   quem gastou sai do registro de envios deste computador (src/consumo.py).
   So na janela do escritorio: o historico mostra o comeco das perguntas de
   cada pessoa.
*/

const pc = { dados: null, aberto: null, historicos: {}, carregando: false };
const PC_ALERTA = 0.8;
const PC_RECARGA_A_PARTIR = 0.7;

async function mostrarConsumo() {
  abrirTela("Plano e consumo", { cheia: true });
  marcarDestino("consumo");
  $("conversa-meta").textContent = "Quanto o escritório usa da IA, quem usa, e os limites";
  cascaConsumo('<p class="nota">lendo…</p>');
  await carregarConsumo(true);
}

async function carregarConsumo(forcar) {
  pc.carregando = true;
  try {
    const r = await fetch("/api/consumo" + (forcar ? "?forcar=true" : ""));
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
function reais(v) { return "R$ " + Number(v || 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 }); }

function desenharConsumo() {
  const d = pc.dados;
  if (!d) {
    cascaConsumo('<p class="pc-vazio">Não consegui ler o consumo: ' + esc(pc.erro || "o servidor não respondeu") + ".</p>");
    return;
  }
  const c = d.conta;
  cascaConsumo(blocoGeral(d, c) + blocoEquipe(d) + blocoLimites(d) + blocoPlano(d, c) + blocoRecarga(c));
  ligarConsumo();
}

/* ------------------------------------------------- 1. o consumo do ciclo */

function blocoGeral(d, c) {
  if (!c) {
    const motivo = d.erro
      ? "Sem conseguir falar com paulus.ia.br agora (" + esc(d.erro) + "): os números do plano voltam quando a internet voltar."
      : "A conta da IA ainda não está ligada neste PAULUS. Ligue com a conta Google em Configurações › Modelos, ou assine em paulus.ia.br/cadastro.";
    return '<section class="pc-geral"><span class="pc-rotulo">Consumo do ciclo</span><p class="pc-texto">' + motivo + "</p>" +
      '<div class="linha-form"><button class="primario" data-pc-ir="modelos">Abrir Configurações › Modelos</button></div></section>';
  }
  const ciclo = c.ciclo || {};
  const t = c.tokens || {};
  const limite = Number(ciclo.tokens || (c.plano || {}).tokens || 0);
  const usados = Number(ciclo.usados || 0);
  const parte = limite ? Math.min(1, usados / limite) : 0;
  const pct = Math.round(parte * 100);
  const classe = parte >= 1 ? " esgotado" : parte >= PC_ALERTA ? " alto" : "";
  const plano = c.cortesia ? "Cortesia" : (c.plano || {}).nome || "Plano";
  const renova = c.plano_vigente && ciclo.fim ? ((c.assinatura || {}).situacao === "authorized" ? "renova em " : "vale até ") + pcData(ciclo.fim) : "sem plano em dia";
  const alertas = (d.painel.alertas || []).map((a) => '<p class="pc-alerta-linha">' + ic("error", 16) + esc(a) + "</p>").join("") +
    (c.plano_vigente ? "" : '<p class="pc-alerta-linha">' + ic("error", 16) + "Sem o plano em dia, o PAULUS funciona sem IA.</p>");
  return '<section class="pc-geral' + classe + '" aria-labelledby="pc-t-geral">' +
    '<div class="pc-geral-topo"><span class="pc-rotulo" id="pc-t-geral">Consumo do ciclo</span>' +
    '<span class="pc-chip">' + esc(plano) + " · " + esc(renova) + "</span></div>" +
    '<div class="pc-numeros"><div class="pc-grande"><b>' + esc(tokCurto(usados)) + "</b><span>de " + esc(tokCurto(limite)) +
    " tokens do plano usados</span></div>" + '<span class="pc-pct">' + pct + "%</span></div>" +
    '<div class="pc-barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + pct + '" aria-label="Uso do ciclo">' +
    '<i style="width:' + pct + '%"></i><span class="pc-marca" style="left:' + PC_ALERTA * 100 + '%" title="80%"></span></div>' +
    '<dl class="pc-fatos">' +
    "<div><dt>Restantes</dt><dd>" + esc(tokCurto(t.restantes || 0)) + "</dd></div>" +
    "<div><dt>Hoje</dt><dd>" + esc(tokCurto(t.hoje || 0)) + "</dd></div>" +
    "<div><dt>Da recarga</dt><dd>" + esc(tokCurto(t.da_recarga || 0)) + "</dd></div>" +
    "<div><dt>" + ((c.assinatura || {}).situacao === "authorized" ? "Renova em" : "Vale até") + "</dt><dd>" + esc(ciclo.fim && c.plano_vigente ? pcData(ciclo.fim) : "—") + "</dd></div>" +
    "</dl>" + alertas + "</section>";
}

/* --------------------------------------------- 2. quem esta consumindo */

function blocoEquipe(d) {
  const p = d.painel;
  const pessoas = (p.pessoas || []).filter((x) => x.tokens > 0 || x.limite);
  const maior = Math.max(1, ...pessoas.map((x) => x.tokens));
  const linhas = pessoas.length ? pessoas.map((x) => {
    const aberto = pc.aberto === x.conta_id;
    const largura = Math.max(x.tokens ? 2 : 0, Math.round((100 * x.tokens) / maior));
    const alerta = x.alerta ? '<span class="pc-aviso' + (/atingiu/.test(x.alerta) ? " no-limite" : "") + '">' + esc(x.alerta) + "</span>" : "";
    return '<div class="pc-pessoa' + (aberto ? " aberta" : "") + '">' +
      '<button type="button" class="pc-pessoa-linha" data-pc-pessoa="' + x.conta_id + '" aria-expanded="' + aberto + '">' +
      '<span class="pc-nome">' + esc(x.nome) + alerta + "</span>" +
      '<span class="pc-trilho"><i style="width:' + largura + '%"></i></span>' +
      '<span class="pc-qtd"><b>' + esc(tokCurto(x.tokens)) + "</b> · " + esc(String(x.porcento).replace(".", ",")) + "%</span>" +
      ic("expand_more", 18) + "</button>" +
      (aberto ? '<div class="pc-historico">' + historicoDe(x.conta_id) + "</div>" : "") + "</div>";
  }).join("") : '<p class="pc-texto">Nenhum envio à nuvem neste ciclo ainda.</p>';
  return '<section class="pc-bloco" aria-labelledby="pc-t-equipe"><div class="pc-cabeca"><h2 id="pc-t-equipe">Quem está consumindo</h2>' +
    "<small>neste ciclo, pelo registro deste computador · " + esc(tokCurto(p.total)) + " tokens no total</small></div>" +
    '<div class="pc-equipe">' + linhas + "</div></section>";
}

function historicoDe(id) {
  const h = pc.historicos[id];
  if (!h) return '<p class="nota">lendo…</p>';
  if (!h.length) return '<p class="pc-texto">Sem envios nos últimos 31 dias.</p>';
  return h.map((dia) => '<div class="pc-dia"><div class="pc-dia-cabeca"><b>' + esc(dia.rotulo) + "</b><span>" + esc(tokCurto(dia.tokens)) + " tokens</span></div>" +
    dia.itens.map((i) => {
      const hora = String(i.quando).slice(11, 16);
      const texto = '<span class="pc-hora">' + esc(hora) + '</span><span class="pc-pergunta">“' + esc(i.pergunta || "sem texto") + '”</span>' +
        '<span class="pc-tok">' + esc(tokCheio(i.tokens)) + " tokens</span>";
      return i.trabalho_id
        ? '<button type="button" class="pc-item" data-pc-conversa="' + esc(i.trabalho_id) + '" title="Abrir a conversa">' + texto + "</button>"
        : '<div class="pc-item">' + texto + "</div>";
    }).join("") + "</div>").join("");
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

/* ------------------------------------------------------ 3. os limites */

function blocoLimites(d) {
  const l = d.painel.limites || {};
  const partes = [];
  if (l.diario) partes.push("diário de " + tokCurto(l.diario));
  if (l.mensal) partes.push("mensal de " + tokCurto(l.mensal));
  const individuais = Object.keys(l.pessoas || {}).length;
  if (individuais) partes.push(individuais === 1 ? "1 limite individual" : individuais + " limites individuais");
  const resumo = partes.length ? "Escritório: " + partes.join(" · ") : "Sem limites: a equipe usa até o fim dos tokens do plano.";
  return '<section class="pc-bloco pc-linha" aria-labelledby="pc-t-limites"><div class="pc-cabeca"><h2 id="pc-t-limites">Limites de uso</h2>' +
    "<small>" + esc(resumo) + "</small></div>" +
    '<button class="com-icone" data-pc-limites="1">' + ic("tune", 16) + "Ajustar limites</button></section>";
}

async function ajustarLimites() {
  const d = pc.dados;
  const l = d.painel.limites || {};
  const pessoas = d.painel.pessoas || [];
  const campo = (chave, valor, rotulo) => '<label class="pc-campo"><span>' + esc(rotulo) + "</span>" +
    '<input type="text" inputmode="numeric" data-dialogo-chave="' + chave + '" value="' + esc(valor ? tokCheio(valor) : "") + '" placeholder="sem limite"></label>';
  const html = '<div class="pc-limites">' +
    '<p class="pc-texto">Tokens por dia e por ciclo. Em branco, sem limite. Passado o limite, a pergunta é escrita pelo modelo deste computador, e a resposta diz por quê.</p>' +
    '<div class="pc-limite-linha"><b>O escritório inteiro</b>' + campo("diario", l.diario, "Diário") + campo("mensal", l.mensal, "No ciclo") + "</div>" +
    pessoas.filter((x) => x.conta_id >= 0).map((x) => {
      const p = (l.pessoas || {})[String(x.conta_id)] || {};
      return '<div class="pc-limite-linha"><b>' + esc(x.nome) + "</b>" + campo("p:" + x.conta_id + ":diario", p.diario, "Diário") +
        campo("p:" + x.conta_id + ":mensal", p.mensal, "No ciclo") + "</div>";
    }).join("") + "</div>";
  const r = await dialogo({ titulo: "Limites de uso", contexto: "Plano e consumo", html: html, confirmar: "Salvar limites", larga: true });
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

/* ------------------------------------------------- 4. o plano e o upgrade */

function blocoPlano(d, c) {
  if (!c) return "";
  const plano = c.plano || {};
  const proximo = c.plano_proximo ? '<span class="pc-proximo">a partir da renovação: ' + esc(c.plano_proximo.nome) + "</span>" : "";
  const linha = c.cortesia ? "Cortesia · " + tokCurto(plano.tokens) + " tokens por ciclo"
    : plano.nome + " · " + tokCurto(plano.tokens) + " tokens por mês · " + reais(plano.valor) + "/mês";
  return '<section class="pc-bloco pc-linha" aria-labelledby="pc-t-plano"><div class="pc-cabeca"><h2 id="pc-t-plano">Seu plano</h2>' +
    "<small>" + esc(linha) + "</small>" + proximo + "</div>" +
    '<div class="pc-acoes"><button data-pc-ir="modelos">Gerenciar plano</button>' +
    (c.cortesia ? "" : '<button class="com-icone" data-pc-upgrade="1">' + ic("arrow_upward", 16) + "Ver upgrade</button>") + "</div></section>";
}

async function verUpgrade() {
  const c = pc.dados.conta || {};
  const atual = (c.plano || {}).id;
  const marcado = (c.plano_proximo || c.plano || {}).id;
  const planos = c.planos || [];
  const ativa = (c.assinatura || {}).situacao === "authorized";
  const linhas = planos.map((p) => {
    const sel = p.id === marcado;
    return '<button type="button" class="pc-opcao' + (sel ? " on" : "") + '" data-pc-opcao="' + esc(p.id) + '">' +
      '<span class="pc-opcao-nome">' + esc(p.nome) + (p.id === atual ? ' <em>seu plano</em>' : "") + "</span>" +
      '<span class="pc-opcao-valor">' + esc(reais(p.valor)) + "<small>/mês</small></span>" +
      '<span class="pc-opcao-tok"><b>' + esc(tokCurto(p.tokens)) + "</b> tokens por mês</span>" +
      '<span class="pc-opcao-uso">~' + esc(Math.round(p.tokens / 3500 / 100) * 100 > 0 ? (Math.round(p.tokens / 3500 / 100) * 100).toLocaleString("pt-BR") : "0") + " perguntas por mês</span></button>";
  }).join("");
  const html = '<div class="pc-upgrade">' + linhas + "</div>" +
    '<input type="hidden" data-dialogo-chave="plano" id="pc-plano-escolhido" value="' + esc(marcado || "") + '">' +
    '<p class="pc-texto">Os planos têm os mesmos recursos e servem à equipe inteira; o que muda é a quantidade de tokens. ' +
    (ativa ? "Trocar vale na próxima renovação: o valor novo é cobrado nela, e os tokens do plano novo entram com ela." : "A assinatura abre no Mercado Pago, onde se põe o cartão.") + "</p>";
  const pedido = dialogo({ titulo: "Planos", contexto: "Plano e consumo", html: html, confirmar: ativa ? "Trocar de plano" : "Assinar", larga: true });
  const veu = document.getElementById("veu-dialogo");
  if (veu) veu.querySelectorAll("[data-pc-opcao]").forEach((b) => {
    b.onclick = () => {
      veu.querySelectorAll("[data-pc-opcao]").forEach((x) => x.classList.toggle("on", x === b));
      veu.querySelector("#pc-plano-escolhido").value = b.dataset.pcOpcao;
    };
  });
  const r = await pedido;
  if (!r || !r.ok || !r.valores.plano) return;
  const escolhido = r.valores.plano;
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

/* ------------------------------------------------ 5. a recarga rapida */

function blocoRecarga(c) {
  if (!c || !c.plano_vigente || c.cortesia) return "";
  const ciclo = c.ciclo || {};
  const limite = Number(ciclo.tokens || 0);
  if (!limite || Number(ciclo.usados || 0) / limite < PC_RECARGA_A_PARTIR) return "";
  const pacotes = c.recargas_pacotes || [];
  if (!pacotes.length) return "";
  return '<section class="pc-recarga" aria-labelledby="pc-t-recarga"><div class="pc-cabeca"><h2 id="pc-t-recarga">Precisando de mais tokens neste ciclo?</h2>' +
    "<small>A recarga entra na hora, no Pix, e não vence na renovação. Não muda o plano.</small></div>" +
    '<div class="pc-acoes">' + pacotes.map((p) => '<button data-pc-recarga="' + esc(p.id) + '">+' + esc(tokCurto(p.tokens)) +
      ' <span class="pc-preco">' + esc(reais(p.valor)) + "</span></button>").join("") + "</div></section>";
}

/* -------------------------------------------------------------- cliques */

function ligarConsumo() {
  const tela = $("pc-tela");
  if (!tela) return;
  tela.querySelectorAll("[data-pc-pessoa]").forEach((b) => { b.onclick = () => abrirHistorico(Number(b.dataset.pcPessoa)); });
  tela.querySelectorAll("[data-pc-conversa]").forEach((b) => {
    b.onclick = async () => { marcarDestino("conversa"); if (!(await abrirTrabalho(b.dataset.pcConversa))) avisoCert("Essa conversa não existe mais."); };
  });
  tela.querySelectorAll("[data-pc-ir]").forEach((b) => { b.onclick = () => { marcarDestino("config"); mostrarConfig(b.dataset.pcIr); }; });
  tela.querySelectorAll("[data-pc-limites]").forEach((b) => { b.onclick = ajustarLimites; });
  tela.querySelectorAll("[data-pc-upgrade]").forEach((b) => { b.onclick = verUpgrade; });
  tela.querySelectorAll("[data-pc-recarga]").forEach((b) => {
    b.onclick = () => recarregarNuvem(() => carregarConsumo(true), b.dataset.pcRecarga);
  });
}
