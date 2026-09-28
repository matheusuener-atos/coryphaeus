/* ------------------------------------------------------------ modelos */
/*
   Configurações › Modelos: os modelos de linguagem do PAULUS (src/modelos.py).
   O motor é o Ollama, nesta máquina; o que esta tela faz é o que antes pedia
   terminal - baixar (com a barra em bytes e o Cancelar), trocar o padrão,
   medir cada modelo NESTA máquina e dizer que modelo faz cada tarefa.

   Baixar, remover, medir e delegar valem na hora: não passam pelo "Salvar
   alterações" da tela, porque não são rascunho - são ações.
*/

const mod = { dados: null, relogio: null, medindo: "" };

async function carregarModelos() {
  try {
    const [r, c] = await Promise.all([fetch("/api/modelos"), fetch("/api/calibracao")]);
    mod.dados = r.ok ? await r.json() : null;
    mod.calib = c.ok ? await c.json() : null;
  } catch (err) {
    mod.dados = null;
  }
}

/* A calibracao compartilhada (src/calibracao_remota.py): desligada de
   fabrica, e a tela mostra exatamente o que vai antes de alguem ligar. */
function blocoCalibracao(c, curto) {
  if (!c) return "";
  const ligado = Boolean(c.participar);
  const quando = ligado && c.ultimo_envio ? " · enviado em " + c.ultimo_envio.slice(8, 10) + "/" + c.ultimo_envio.slice(5, 7) : "";
  const outras = ligado && c.de_outras_maquinas ? " · " + plural(c.de_outras_maquinas, "medida") + " de outras máquinas" : "";
  return '<div class="ag-toggle' + (ligado ? " on" : "") + '" data-cal-participar="1" role="switch" tabindex="0" aria-checked="' + ligado + '">' +
    '<span class="duas-linhas"><b>Participar da calibração</b><small>' +
    (curto ? "mede o modelo desta máquina uma vez (cerca de um minuto), manda as medidas ao site do PAULUS e recebe as de outras; nada do escritório"
      : "mede sozinho, uma vez, cada modelo que você baixar e manda ao site do PAULUS as medidas desta máquina — processador, memória, as duas velocidades e as palavras por segundo de cada modelo — e recebe as de outras máquinas. Nada do escritório, nada de pessoa") +
    esc(quando + outras) + "</small></span><i></i></div>" +
    '<p class="cfg-explica"><button type="button" class="em-ligacao" data-cal-ver="1">ver o que é enviado</button>' +
    (c.erro ? " · " + esc(c.erro) : "") + "</p>";
}

function ligarCalibracao(raiz, depois) {
  const r = raiz || document;
  r.querySelectorAll("[data-cal-participar]").forEach((t) => {
    t.onclick = async () => {
      const ligar = !t.classList.contains("on");
      t.classList.toggle("on", ligar);
      const resp = await fetch("/api/calibracao", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ participar: ligar }) });
      if (resp.ok) mod.calib = await resp.json();
      avisoCert(ligar ? "participando da calibração — as medidas desta máquina vão ao site do PAULUS" : "calibração desligada: nada mais sai desta máquina por ela", { tom: "ok" });
      if (depois) depois();
    };
  });
  r.querySelectorAll("[data-cal-ver]").forEach((b) => {
    b.onclick = async () => {
      let c = mod.calib;
      try { c = await (await fetch("/api/calibracao")).json(); mod.calib = c; } catch (err) { /* fica o que havia */ }
      const vai = (c && c.o_que_vai) || [];
      dialogo({
        titulo: "O que a calibração envia", contexto: "Configurações › Modelos", cancelar: "Fechar", larga: true,
        texto: vai.length
          ? "Isto, e só isto, vai para " + c.endereco + " — uma linha por modelo medido nesta máquina:"
          : "Nenhum modelo foi medido nesta máquina ainda. Quando você clicar em Medir, a medida entra aqui — e é isso que vai.",
        html: vai.length ? '<pre class="cal-json">' + esc(JSON.stringify(vai, null, 2)) + "</pre>" : "",
      });
    };
  });
}

function gbBR(gb) {
  if (gb === null || gb === undefined) return "tamanho a confirmar";
  return String(gb).replace(".", ",") + " GB";
}

const ROTULO_TAREFA = {};

/* O tempo que o modelo deve levar aqui (src/maquina.py) e a nota no nosso
   banco de provas. "Estimativa" ate alguem medir; depois, "medido". */
function textoDaEstimativa(m) {
  const e = m.estimativa;
  const partes = [];
  if (e) {
    if (!e.cabe) partes.push("não cabe na memória desta máquina");
    else if (e.primeira_s) {
      partes.push((e.fonte === "medido" ? "medido aqui" : "estimativa") + ": 1ª pergunta ~" + e.primeira_s + " s, seguintes ~" + e.seguinte_s + " s");
    }
  }
  if (m.qualidade) partes.push("acertou " + m.qualidade.certas + " de " + m.qualidade.total + " no nosso teste");
  else if (e) partes.push("ainda sem nota no nosso teste");
  return partes.join(" · ");
}

function cartaoMaquina(d) {
  const m = d.maquina;
  const conferir = mod.testando ? "<button disabled>conferindo…</button>" : '<button data-mod-testar="1">' + (m ? "Conferir de novo" : "Conferir esta máquina") + "</button>";
  if (!m) {
    return cartaoCfg("Esta máquina", metaCfg("sem IA, uns 5 segundos"),
      '<p class="cfg-texto">Ainda não conferi esta máquina. O teste mede a memória e o processador, sem rodar modelo, e estima quanto cada modelo demora aqui.</p>' +
      '<div class="cfg-botoes">' + conferir + "</div>");
  }
  const gb = (x) => String(x).replace(".", ",") + " GB";
  const placas = (m.placas_nvidia || []).map((p) => p.nome + " · " + gb(p.memoria_gb)).join("; ");
  const num = (x) => String(x).replace(".", ",");
  const ficha = fichaCfg([
    ["Memória", gb(m.ram_total_gb)],
    ["Livre agora", gb(m.ram_livre_gb)],
    ["A memória lê", num(m.banda_gbs) + " GB/s"],
    ["Contas", Math.round(m.gflops) + " bi/s"],
  ]);
  const quem = [m.processador, placas ? "placa " + placas : "sem placa NVIDIA",
    m.na_bateria ? "na bateria" : (m.na_bateria === false ? "na tomada" : "")].filter(Boolean).join(" · ");
  return cartaoCfg("Esta máquina", metaCfg("conferida em " + dataCurtaMat(m.quando)),
    '<p class="cfg-explica">' + esc(quem) + "</p>" + ficha + (d.recomendado ? '<p class="cfg-explica"><b>Recomendado: ' + esc(d.recomendado) + "</b> — " + esc(d.porque) + ".</p>" : (d.porque ? '<p class="cfg-explica">' + esc(d.porque) + ".</p>" : "")) +
    '<p class="cfg-explica">Os tempos são estimativas, tiradas do teste desta máquina e de modelos medidos em outras. ' +
    "Medir um modelo aqui corrige a estimativa de todos." + (m.na_bateria ? " Na bateria o Windows segura o processador: na tomada fica mais rápido." : "") + "</p>" +
    '<div class="cfg-botoes">' + conferir + "</div>" + blocoCalibracao(mod.calib, false));
}

function secaoModelos() {
  const d = mod.dados;
  if (!d) return aberturaCfg() + '<p class="nota">lendo os modelos…</p>';
  (d.tarefas || []).forEach((t) => { ROTULO_TAREFA[t.id] = t.rotulo; });
  if (!d.rodando) {
    return aberturaCfg() + cartaoCfg("O Ollama não está respondendo", "",
      '<p class="cfg-texto">Os modelos moram no Ollama, nesta máquina, e ele não respondeu agora. ' +
      "Abra o Assistente: o cartão do motor tem o botão para ligá-lo.</p>");
  }
  const b = d.baixando || {};
  const total = (d.instalados || []).reduce((s, m) => s + (m.gb || 0), 0);
  const ficha = fichaCfg([
    ["Padrão", d.padrao],
    ["Instalados", String((d.instalados || []).length)],
    ["Em disco", gbBR(Math.round(total * 10) / 10)],
    ["Baixando", b.andando ? b.modelo + " · " + (b.progresso || 0) + "%" : "nada"],
    ["Recomendado", d.recomendado || "—"],
  ]);

  const instalados = (d.instalados || []).map((m) => {
    const md = m.medida;
    const medida = md ? " · " + String(md.tokens_por_segundo).replace(".", ",") + " palavras/s, carrega em " +
      String(md.carregar_s).replace(".", ",") + " s (medido em " + esc(md.quando.slice(8, 10) + "/" + md.quando.slice(5, 7)) + ")" : "";
    const estimativa = textoDaEstimativa(m);
    const sub = [m.parametros, m.quantizacao, gbBR(m.gb)].filter(Boolean).join(" · ") + medida;
    const marcas = (m.recomendado ? '<span class="etiqueta">recomendado</span>' : "") + (m.padrao ? '<span class="etiqueta">padrão</span>' : "") +
      (m.tarefas || []).map((t) => '<span class="etiqueta">' + esc(ROTULO_TAREFA[t] || t) + "</span>").join("");
    const medir = mod.medindo === m.nome
      ? '<button disabled>medindo…</button>'
      : '<button data-mod-medir="' + esc(m.nome) + '"' + (mod.medindo ? " disabled" : "") + ">Medir</button>";
    return '<div class="cfg-servico mod-linha"><span class="caixa-tipo">' + ic("memory", 18) + "</span>" +
      '<span class="duas-linhas cresce"><b>' + esc(m.nome) + "</b><small>" + esc(sub) + "</small>" +
      (estimativa ? "<small>" + esc(estimativa) + "</small>" : "") + "</span>" +
      '<span class="mod-marcas">' + marcas + "</span>" + medir +
      '<button class="mais-linha" data-mod-mais="' + esc(m.nome) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");

  const opcoes = (atual) => '<option value="">Padrão (' + esc(d.padrao) + ")</option>" +
    (d.instalados || []).filter((m) => !m.padrao).map((m) =>
      '<option value="' + esc(m.nome) + '"' + (m.nome === atual ? " selected" : "") + ">" + esc(m.nome) + "</option>").join("");
  const tarefas = (d.tarefas || []).map((t) =>
    '<div class="cfg-servico mod-tarefa"><span class="duas-linhas cresce"><b>' + esc(t.rotulo) + "</b><small>" + esc(t.explica) + "</small></span>" +
    '<select data-mod-tarefa="' + esc(t.id) + '" aria-label="Modelo para ' + esc(t.rotulo) + '">' + opcoes(t.modelo) + "</select></div>").join("");

  const andamento = b.andando
    ? '<div class="mod-baixando"><span class="duas-linhas cresce"><b>Baixando ' + esc(b.modelo) + "</b><small>" +
      esc(b.fase || "") + (b.total_gb ? " · " + gbBR(b.baixado_gb) + " de " + gbBR(b.total_gb) : "") + "</small></span>" +
      '<b class="mod-pct">' + (b.progresso || 0) + '%</b><button data-mod-cancelar="1">Cancelar</button>' +
      '<div class="progresso mod-progresso"><i style="width:' + (b.progresso || 0) + '%"></i></div></div>'
    : (b.erro ? '<p class="cfg-explica mod-erro">O download de ' + esc(b.modelo) + " parou: " + esc(b.erro) + ".</p>" : "");
  const catalogo = (d.catalogo || []).filter((c) => !c.instalado).map((c) =>
    '<div class="cfg-servico"><span class="caixa-tipo">' + ic("download", 18) + "</span>" +
    '<span class="duas-linhas cresce"><b>' + esc(c.nome) + " · " + esc(gbBR(c.gb)) + (c.recomendado ? " · recomendado" : "") + "</b><small>" + esc(c.papel) +
    (textoDaEstimativa(c) ? " " + esc(textoDaEstimativa(c)) + "." : "") + "</small></span>" +
    '<button data-mod-baixar="' + esc(c.nome) + '"' + (b.andando ? " disabled" : "") + ">Baixar</button></div>").join("");
  const outro = '<div class="linha-form mod-outro"><input type="text" id="mod-outro" placeholder="outro modelo do Ollama, por exemplo qwen2.5:1.5b" autocomplete="off" spellcheck="false">' +
    '<button data-mod-baixar-outro="1"' + (b.andando ? " disabled" : "") + ">Baixar</button></div>";

  return aberturaCfg() + ficha + cartaoMaquina(d) +
    cartaoCfg("Nesta máquina", metaCfg("o padrão faz toda tarefa sem modelo próprio"),
      '<div class="cfg-linhas">' + instalados + "</div>" +
      '<p class="cfg-explica">Medir faz uma resposta curta e fixa e mostra quantas palavras por segundo saem nesta máquina. É esse número que ajuda a decidir, mais que o tamanho.</p>') +
    cartaoCfg("Quem faz cada tarefa", metaCfg("vale na hora"), '<div class="cfg-linhas">' + tarefas + "</div>" +
      '<p class="cfg-explica">Um modelo leve nos julgamentos rápidos deixa a conversa mais ágil; um maior nas perguntas sobre documentos lê melhor e demora mais. Meça antes de escolher.</p>') +
    cartaoBusca(d, b) +
    cartaoCfg("Baixar", metaCfg("do registro público do Ollama"), andamento + '<div class="cfg-linhas">' + catalogo + "</div>" + outro +
      '<p class="cfg-explica">O download é do Ollama, direto do registro dele, e fica nesta máquina. Cancelar guarda o que já veio: baixar de novo continua de onde parou.</p>');
}

/* A busca por sentido (I7, src/denso.py): um modelo pequeno que transforma
   cada trecho do Acervo num vetor, para achar o assunto mesmo sem a palavra.
   Não responde pergunta — por isso fica fora da lista de modelos. O download
   só acontece pelo botão, com o tamanho dito antes. */
function cartaoBusca(d, b) {
  const s = d.busca;
  if (!s) return "";
  let estado;
  if (!s.instalado) {
    estado = '<div class="cfg-servico"><span class="caixa-tipo">' + ic("download", 18) + "</span>" +
      '<span class="duas-linhas cresce"><b>' + esc(s.modelo) + " · " + esc(gbBR(s.gb)) + "</b>" +
      "<small>Ainda não está nesta máquina. Sem ele, a busca continua pelas palavras.</small></span>" +
      '<button data-mod-baixar="' + esc(s.modelo) + '"' + (b.andando ? " disabled" : "") + ">Baixar</button></div>";
  } else {
    const a = s.andamento || {};
    const feitos = s.vetores != null ? s.vetores : 0;
    const sub = a.andando
      ? "preparando o Acervo: " + milhar(a.feitos || 0) + " de " + milhar(a.total || 0) + " trechos (pausa quando alguém pergunta)"
      : (a.erro ? "parou: " + a.erro : milhar(feitos) + " de " + milhar(s.trechos) + " trechos com vetor");
    estado = '<div class="cfg-servico"><span class="caixa-tipo">' + ic("insights", 18) + "</span>" +
      '<span class="duas-linhas cresce"><b>' + esc(s.modelo) + (s.ligada ? "" : " · desligada") + "</b><small>" +
      esc(sub) + "</small></span></div>";
  }
  return cartaoCfg("Busca por sentido", metaCfg("opcional · roda nesta máquina"),
    '<div class="cfg-linhas">' + estado + "</div>" +
    '<p class="cfg-explica">Acha o trecho pelo assunto, mesmo quando a pergunta usa outras palavras — "quanto custa sair antes?" encontra a cláusula de rescisão. ' +
    "Os vetores são feitos aqui, em segundo plano, e nenhum texto sai da máquina.</p>");
}

function acompanharDownload() {
  clearInterval(mod.relogio);
  mod.relogio = setInterval(async () => {
    if (cfg.secao !== "modelos" || !$("cfg-tela")) { clearInterval(mod.relogio); mod.relogio = null; return; }
    let b;
    try { b = await (await fetch("/api/modelos/baixar")).json(); } catch (err) { return; }
    if (mod.dados) mod.dados.baixando = b;
    if (!b.andando) {
      clearInterval(mod.relogio);
      mod.relogio = null;
      if (b.pronto) avisoCert(b.modelo + " baixado — já dá para usar", { tom: "ok" });
      else if (b.cancelado) avisoCert("download de " + b.modelo + " cancelado");
      await carregarModelos();
    }
    desenharConfig();
  }, 1000);
}

async function modPost(url, corpo) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  return r.json();
}

async function baixarModelo(nome) {
  if (!nome) return;
  const d = await modPost("/api/modelos/baixar", { nome: nome });
  if (!d) return;
  if (mod.dados) mod.dados.baixando = d;
  desenharConfig();
  acompanharDownload();
}

function menuDoModelo(botao, nome) {
  const m = ((mod.dados || {}).instalados || []).find((x) => x.nome === nome);
  if (!m) return;
  const itens = [];
  if (!m.padrao) {
    itens.push({ rotulo: "Usar como padrão", icone: "check", acao: async () => {
      if (await modPost("/api/modelos/padrao", { nome: nome })) {
        avisoCert(nome + " agora é o padrão", { tom: "ok" });
        cfg.recarregar = true;
        await carregarModelos();
        desenharConfig();
      }
    } });
  }
  itens.push({ rotulo: "Medir nesta máquina", icone: "speed", acao: () => medirModelo(nome) });
  if (!m.padrao) {
    itens.push("-", { rotulo: "Remover", icone: "delete", perigo: true, acao: async () => {
      const ok = await confirmar({
        titulo: "Remover " + nome + "?", contexto: "Configurações › Modelos",
        texto: "O modelo sai do Ollama e libera " + gbBR(m.gb) + ". Tarefas que usavam ele voltam para o padrão. Para usar de novo, é baixar outra vez.",
        confirmar: "Remover", perigo: true,
      });
      if (!ok) return;
      const r = await modPost("/api/modelos/remover", { nome: nome });
      if (r) {
        avisoCert(nome + " removido" + (r.tarefas_de_volta_ao_padrao.length ? " — as tarefas dele voltaram ao padrão" : ""), { tom: "ok" });
        await carregarModelos();
        desenharConfig();
      }
    } });
  }
  menuNaLinha(botao, itens);
}

async function medirModelo(nome) {
  mod.medindo = nome;
  desenharConfig();
  const r = await modPost("/api/modelos/medir", { nome: nome });
  mod.medindo = "";
  if (r) avisoCert(nome + ": " + String(r.medida.tokens_por_segundo).replace(".", ",") + " palavras por segundo nesta máquina", { tom: "ok" });
  await carregarModelos();
  desenharConfig();
}

async function testarMaquina() {
  mod.testando = true;
  desenharConfig();
  const r = await modPost("/api/maquina/testar");
  mod.testando = false;
  if (r) avisoCert("máquina conferida" + (r.recomendado ? " — recomendado: " + r.recomendado : ""), { tom: "ok" });
  await carregarModelos();
  desenharConfig();
}

function ligarModelos() {
  const raiz = $("cfg-tela");
  if (!raiz) return;
  ligarCalibracao(raiz, () => desenharConfig());
  const testar = raiz.querySelector("[data-mod-testar]");
  if (testar) testar.onclick = () => testarMaquina();
  raiz.querySelectorAll("[data-mod-baixar]").forEach((b) => { b.onclick = () => baixarModelo(b.dataset.modBaixar); });
  const outro = raiz.querySelector("[data-mod-baixar-outro]");
  if (outro) outro.onclick = () => baixarModelo(($("mod-outro").value || "").trim().toLowerCase());
  const campo = $("mod-outro");
  if (campo) campo.onkeydown = (e) => { if (e.key === "Enter") baixarModelo(campo.value.trim().toLowerCase()); };
  const cancelar = raiz.querySelector("[data-mod-cancelar]");
  if (cancelar) cancelar.onclick = () => modPost("/api/modelos/cancelar");
  raiz.querySelectorAll("[data-mod-medir]").forEach((b) => { b.onclick = () => medirModelo(b.dataset.modMedir); });
  raiz.querySelectorAll("[data-mod-mais]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); menuDoModelo(b, b.dataset.modMais); };
  });
  raiz.querySelectorAll("[data-mod-tarefa]").forEach((s) => {
    melhorarSelect(s);
    s.onchange = async () => {
      const r = await modPost("/api/modelos/tarefa", { tarefa: s.dataset.modTarefa, modelo: s.value });
      if (r) avisoCert((ROTULO_TAREFA[r.tarefa] || r.tarefa) + " agora usa " + r.em_uso, { tom: "ok" });
      await carregarModelos();
      desenharConfig();
    };
  });
  if (mod.dados && mod.dados.baixando && mod.dados.baixando.andando && !mod.relogio) acompanharDownload();
}
