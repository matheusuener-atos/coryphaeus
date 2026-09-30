/* ------------------------------------------- sobre esta resposta (C3) */
/*
   Chave conversa.painel (docs/PROGRESSO-CONVERSA.md, C3).

   O painel da direita deixa de misturar estado global com a ultima resposta
   que teve fontes: ele descreve UMA resposta - a ultima, ou a que a pessoa
   clicar ("ver fontes"). Quatro partes: as fontes que a resposta citou (as
   marcas [Tn] dela; sem marcas, os trechos lidos), as tambem lidas,
   recolhidas, como respondi e onde procurei. Motor, trechos indexados e pasta
   so aparecem no modo de diagnostico (conversa.diagnostico).

   Tambem aqui: a barra acima do campo, que passa a dizer onde a proxima
   pergunta procura (e, com uma resposta andando, o que ela esta fazendo, com
   o Parar); e o que e de cada conversa - rascunho, anexos e rolagem nesta
   janela (localStorage), o modo de escopo no servidor.
*/

/* painelNovo() e diagnostico() moram em 00-base.js: os arquivos que carregam
   antes deste ja os chamam na abertura. */

/* Os numeros [Tn] que a resposta citou, na ordem em que aparecem. */
function marcasDaResposta(texto) {
  const vistos = [];
  String(texto || "").replace(/\[T(\d{1,3})\]/g, (_, n) => {
    const i = Number(n) - 1;
    if (!vistos.includes(i)) vistos.push(i);
    return "";
  });
  return vistos;
}

/* A resposta que o painel descreve: a clicada, ou a ultima com fontes (e,
   sem nenhuma com fontes, a ultima do assistente). */
function respostaPadrao(t) {
  const msgs = (t && t.mensagens) || [];
  for (let i = msgs.length - 1; i >= 0; i--) if (msgs[i].autor === "paulus" && (msgs[i].fontes || []).length) return i;
  for (let i = msgs.length - 1; i >= 0; i--) if (msgs[i].autor === "paulus") return i;
  return -1;
}

function perguntaAntesDe(t, i) {
  const msgs = (t && t.mensagens) || [];
  for (let j = i - 1; j >= 0; j--) if (msgs[j].autor === "pessoa") return msgs[j].texto;
  return "";
}

function selecionarResposta(i, abrirPainel) {
  const t = estado.trabalho;
  if (!t || i < 0 || !t.mensagens[i]) { desenharSobre(null); return; }
  estado.respostaSel = i;
  document.querySelectorAll("#centro .resposta.selecionada").forEach((el) => el.classList.remove("selecionada"));
  const el = document.querySelector('#centro .resposta[data-msg="' + i + '"]');
  if (el) el.classList.add("selecionada");
  desenharSobre(t.mensagens[i], perguntaAntesDe(t, i), el ? el.querySelector(".visor-caixa") : null);
  if (abrirPainel) {
    mostrarLateral(true);
    alternarRamo($("lat-trechos-cabeca"), true);
    $("lat-trechos").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/* O painel de uma resposta guardada (ou nada: `m` nulo esconde as partes). */
function desenharSobre(m, pergunta, visor) {
  const partes = ["lat-lidas", "lat-como", "lat-onde"].map((id) => $(id)).filter(Boolean);
  if (!m) {
    partes.forEach((p) => { p.hidden = true; });
    desenharTrechos([], "", null);
    return;
  }
  const fontes = m.fontes || [];
  const marcas = marcasDaResposta(m.texto).filter((i) => fontes[i]);
  const citadas = marcas.length ? marcas : fontes.map((_, i) => i);
  const lidas = marcas.length ? fontes.map((_, i) => i).filter((i) => !marcas.includes(i)) : [];
  desenharTrechos(citadas.map((i) => fontes[i]), pergunta, visor, citadas.map((i) => i + 1));
  const titulo = $("lat-trechos-titulo");
  if (titulo) titulo.textContent = marcas.length ? "Fontes citadas" : "Trechos lidos";

  // Tambem lidas: o que foi ao modelo e a resposta nao citou, recolhido.
  const blocoLidas = $("lat-lidas");
  if (blocoLidas) {
    blocoLidas.hidden = !lidas.length;
    $("lat-lidas-conta").textContent = lidas.length || "";
    $("lat-lidas-lista").innerHTML = lidas.map((i) => {
      const f = fontes[i];
      return '<div class="lat-lida"><span class="cit">' + (i + 1) + "</span><span>" + prefixoDaFonte(f) + esc(f.documento) +
        " · " + esc(f.onde || ("trecho " + f.trecho)) + "</span></div>";
    }).join("");
  }

  // Como respondi: da propria resposta, e nao do estado de agora.
  const c = (m.cobertura || {}).como || {};
  const linhas = [];
  const frase = fraseDoComo(c, m.segundos || 0);
  if (frase) linhas.push(["Caminho", frase.replace(/, em [\d,]+ s$/, "")]);
  if (m.segundos) linhas.push(["Tempo", segundosBR(m.segundos)]);
  if (c.modelo && !(c.caminho === "nivel0" && c.molde)) linhas.push(["Modelo", c.modelo]);
  if (c.truncou || (m.cobertura || {}).truncou) linhas.push(["Texto", "não coube inteiro na janela do modelo; ele leu o final"]);
  if (c.continuacao) linhas.push(["Pergunta", "entendida como continuação da anterior"]);
  if (m.interrompida) linhas.push(["Situação", "parada no meio"]);
  if (c.agente) linhas.push(["Agente", c.agente + (c.agente_versao ? " · versão " + c.agente_versao : "")]);
  // D4: onde foi escrita e por quê (js/61-aparelho-tela.js).
  if (c.escrita && typeof fraseDaEscrita === "function") linhas.push(["Escrita", fraseDaEscrita(c.escrita)]);
  // L1: a nota que a pessoa deu a esta resposta (js/63-aprendizado.js).
  const nota = typeof avaliacaoDaResposta === "function" && estado.respostaSel !== undefined ? avaliacaoDaResposta(estado.respostaSel) : "";
  if (nota) linhas.push(["Avaliação", nota]);
  const blocoComo = $("lat-como");
  if (blocoComo) {
    blocoComo.hidden = !linhas.length;
    $("lat-como-lista").innerHTML = linhas.map(([k, v]) => "<div><span>" + esc(k) + '</span><span class="valor-prop">' + esc(v) + "</span></div>").join("");
  }

  // Onde procurei: o escopo daquela resposta.
  const blocoOnde = $("lat-onde");
  if (blocoOnde) {
    const e = c.escopo || null;
    const cob = m.cobertura || {};
    let onde = "";
    if (e && (e.apenas || []).length) onde = "Só em " + nomesCurtos(e.apenas) + ".";
    else if (e && e.sem_anexo) onde = "Perguntei onde procurar antes de ler.";
    else if (e && e.tudo) onde = "Em todo o Acervo" + (cob.total_contratos ? " (" + plural(cob.total_contratos, "documento") + ")" : "") + ".";
    else if (cob.total_contratos) onde = "Nos " + plural(cob.total_contratos, "documento") + " abertos.";
    if (onde && (cob.consultados || []).length) onde += " Achei trecho em " + plural(cob.consultados.length, "documento") + ".";
    blocoOnde.hidden = !onde;
    $("lat-onde-texto").textContent = onde;
  }
}

function nomesCurtos(nomes) {
  const n = (nomes || []).filter(Boolean);
  if (n.length <= 5) return n.map((x) => "“" + x + "”").join(", ");
  return n.slice(0, 5).map((x) => "“" + x + "”").join(", ") + " e mais " + (n.length - 5);
}

/* ------------------------------------------ a barra acima do campo */

/* O que vai acontecer com a proxima pergunta, em palavras. */
function textoDoProximo() {
  if (estado.escopo.length) {
    return estado.escopo.length === 1 ? "A próxima pergunta lê só “" + estado.escopo[0] + "”" : "A próxima pergunta lê só os " + plural(estado.escopo.length, "anexo");
  }
  const modo = modoDoEscopo();
  if (modo === "foco") return estado.foco.length === 1 ? "A próxima pergunta lê só “" + estado.foco[0] + "”" : "A próxima pergunta lê os " + plural(estado.foco.length, "documento") + " da conversa";
  if (modo === "perguntar") return "Na próxima pergunta, eu pergunto onde procurar";
  return "A próxima pergunta procura em todo o Acervo" + (estado.contratos ? " · " + plural(estado.contratos, "documento") : "");
}

function desenharBarra() {
  if (!painelNovo()) return;
  const caixa = $("registro");
  if (!caixa) return;
  const agora = $("registro-agora");
  const ponto = caixa.querySelector(".ponto");
  $("atividade").hidden = true;
  caixa.classList.remove("aberto");
  caixa.classList.add("barra-escopo");
  const seta = caixa.querySelector(".registro-seta");
  if (seta) seta.hidden = true;
  if (!estado.trabalhoId) { caixa.hidden = true; return; }
  caixa.hidden = false;
  const andando = estado.ocupado && estado.respondendoId === estado.trabalhoId;
  if (ponto) ponto.classList.toggle("pulsa", andando);
  caixa.classList.toggle("andando", andando);
  agora.innerHTML = andando
    ? esc(estado.linhaViva || "Trabalhando…") + ' <button class="barra-parar" data-barra-parar="1">' + ic("stop", 14) + "Parar</button>"
    : esc(textoDoProximo()) + barraDoAgente();
  const parar = agora.querySelector("[data-barra-parar]");
  if (parar) parar.onclick = (e) => { e.stopPropagation(); pararResposta(); };
  const sel = agora.querySelector("[data-barra-agente]");
  if (sel) {
    sel.onclick = (e) => e.stopPropagation();
    sel.onchange = () => { estado.agenteDecisao = sel.value || "nenhum"; desenharBarra(); $("pedido").focus(); };
  }
}

/* ------------------------------------------ o agente da proxima pergunta (A2) */

/* O agente que a proxima pergunta vai usar: o que a pessoa escolheu, ou o
   que a regra sugeriu (GET /api/agentes/sugerir), mostrado ANTES de enviar,
   com um seletor para trocar ou nao usar. */
function agenteDaVez() {
  const ativos = estado.agentesAtivos || [];
  if (estado.agenteDecisao === "nenhum") return null;
  if (estado.agenteDecisao) return ativos.find((a) => a.slug === estado.agenteDecisao) || null;
  return estado.agenteSugerido || null;
}

function barraDoAgente() {
  const ativos = estado.agentesAtivos || [];
  if (!ativos.length) return "";
  const vez = agenteDaVez();
  // A4: quem precisa de revisao continua no seletor (a escolha pelo nome vale),
  // marcado; e, quando a regra o apontaria, a barra diz por que nao o usou.
  const opcoes = ['<option value="nenhum"' + (vez ? "" : " selected") + ">sem agente</option>"].concat(
    ativos.map((a) => '<option value="' + esc(a.slug) + '"' + (vez && vez.slug === a.slug ? " selected" : "") + ">" + esc(a.nome) +
      (a.precisa_revisao ? " (precisa de revisão)" : "") + "</option>"));
  const revisao = !vez && !estado.agenteDecisao && (estado.agentesEmRevisao || []).length
    ? ' <span class="barra-revisao" data-barra-revisao="1">· “' + esc(estado.agentesEmRevisao[0].nome) + "” precisa de revisão: não escolhi sozinho</span>"
    : "";
  return ' · <span class="barra-agente">' + (vez ? (estado.agenteDecisao ? "Usando: " : "Usando (pelo pedido): ") : "Agente: ") +
    '<select data-barra-agente="1" aria-label="Agente da próxima pergunta">' + opcoes.join("") + "</select>" + revisao + "</span>";
}

function agenteDoEnvio() {
  if (!painelNovo()) return {};
  const decisao = estado.agenteDecisao, sugerido = estado.agenteSugerido;
  estado.agenteDecisao = "";
  estado.agenteSugerido = null;
  if (decisao === "nenhum") return { sem_agente: true };
  if (decisao) return { agente: decisao };
  if (sugerido) return { agente: sugerido.slug };
  return {};
}

let sugestaoTimer = null;
$("pedido").addEventListener("input", () => {
  if (!painelNovo() || !estado.trabalhoId && !$("pedido").value) return;
  clearTimeout(sugestaoTimer);
  sugestaoTimer = setTimeout(async () => {
    const texto = $("pedido").value.trim();
    try {
      const d = await (await fetch("/api/agentes/sugerir?texto=" + encodeURIComponent(texto))).json();
      if (!d || !d.ligado) { estado.agentesAtivos = []; estado.agenteSugerido = null; desenharBarra(); return; }
      estado.agentesAtivos = d.ativos || [];
      estado.agenteSugerido = d.agente || null;
      estado.agentesEmRevisao = d.em_revisao || [];
      if (!texto) estado.agenteDecisao = "";
      desenharBarra();
    } catch (err) { /* sem sugestao: a pergunta vai como sempre */ }
  }, 350);
});

/* ------------------------------------------ o que e de cada conversa */

function chaveDaConversa(id) {
  return "paulus.conversa." + id;
}

function lerDaConversa(id) {
  if (!id) return {};
  try { return JSON.parse(localStorage.getItem(chaveDaConversa(id)) || "{}") || {}; } catch (err) { return {}; }
}

function gravarNaConversa(id, dados) {
  if (!id) return;
  try { localStorage.setItem(chaveDaConversa(id), JSON.stringify(Object.assign(lerDaConversa(id), dados))); } catch (err) { /* sem memoria */ }
}

/* Ao sair de uma conversa: o rascunho, os anexos pendentes e a rolagem ficam
   com ela, e nao com a proxima. */
function guardarDaConversa(id) {
  if (!painelNovo() || !id) return;
  gravarNaConversa(id, { rascunho: $("pedido").value, anexos: estado.escopo.slice(), rolagem: $("fluxo").scrollTop });
}

/* Ao abrir: o que era dela volta. O modo de escopo vem do servidor. */
function restaurarDaConversa(t) {
  if (!painelNovo() || !t) return null;
  const s = lerDaConversa(t.id);
  $("pedido").value = s.rascunho || "";
  $("pedido").style.height = "auto";
  const abertos = new Set((estado.abertos || []).map((d) => d.nome || d.name || d));
  const anexos = (s.anexos || []).filter((n) => !abertos.size || abertos.has(n));
  definirEscopo(anexos);
  const modo = (t.contexto || {}).modo_escopo;
  if (modo && (modo !== "foco" || (estado.foco || []).length)) { estado.modoEscopo = modo; desenharEscopo(); }
  return s;
}

function restaurarRolagem(s) {
  if (!painelNovo() || !s || s.rolagem == null) return;
  $("fluxo").scrollTop = s.rolagem;
  atualizarIrAoFim();
}

let rascunhoTimer = null;
$("pedido").addEventListener("input", () => {
  if (!painelNovo() || !estado.trabalhoId) return;
  clearTimeout(rascunhoTimer);
  const id = estado.trabalhoId;
  rascunhoTimer = setTimeout(() => gravarNaConversa(id, { rascunho: $("pedido").value }), 300);
});

function guardarModoNoServidor() {
  if (!painelNovo() || !estado.trabalhoId) return;
  fetch("/api/trabalhos/" + estado.trabalhoId + "/escopo", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ modo: modoDoEscopo() }),
  }).catch(() => { /* fica so nesta janela */ });
}

/* ------------------------------------------ duas perguntas ao mesmo tempo */

/* Com uma resposta andando nesta pagina, a segunda pergunta diz por que nao
   foi, e oferece esperar: ela vai sozinha quando a primeira terminar. */
function avisarOcupado(texto) {
  const id = estado.respondendoId;
  const r = (estado.recentes || []).find((x) => x.id === id);
  const titulo = r ? r.titulo : (estado.trabalho && estado.trabalho.id === id ? estado.trabalho.titulo : "");
  avisoCert("A conversa " + (titulo ? "“" + titulo + "” " : "") + "ainda está respondendo.", {
    acao: { rotulo: "Esperar na fila", fazer: () => {
      estado.naEspera = { texto: texto, conversa: estado.trabalhoId };
      $("pedido").value = "";
      gravarNaConversa(estado.trabalhoId, { rascunho: "" });
      avisoCert("Mando esta pergunta assim que a outra terminar.");
    } },
  });
}

function soltarEspera() {
  const e = estado.naEspera;
  if (!e || estado.ocupado) return;
  estado.naEspera = null;
  if (estado.trabalhoId !== e.conversa) return;
  enviar({ texto: e.texto });
}

/* A resposta ao vivo nao sabia o indice dela na conversa: ao terminar, as
   respostas da pagina ganham o data-msg da mensagem guardada, na ordem. */
function marcarRespostasGuardadas(t) {
  const indices = ((t && t.mensagens) || []).map((m, i) => (m.autor === "paulus" ? i : -1)).filter((i) => i >= 0);
  const blocos = [...document.querySelectorAll("#centro > .resposta, #centro .resposta")].filter((el, k, todos) => todos.indexOf(el) === k);
  const soltos = blocos.filter((el) => el.dataset.msg === undefined);
  if (!soltos.length) return;
  const ja = blocos.filter((el) => el.dataset.msg !== undefined).length;
  soltos.forEach((el, k) => { if (indices[ja + k] !== undefined) el.dataset.msg = String(indices[ja + k]); });
}

$("lat-lidas-cabeca").onclick = () => alternarRamo($("lat-lidas-cabeca"));
