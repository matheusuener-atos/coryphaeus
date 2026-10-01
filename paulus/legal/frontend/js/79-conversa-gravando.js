/* ------------------------------------- gravar dentro da conversa */
/*
   Pacote de telas de 01/10/2026 (`Conversa - Gravando`): "grave a reuniao
   com a Rio Fresco e me ajude a responder". A conversa grava ali mesmo - o
   gravador de sempre (js/11-gravacoes.js, gv.vivo) -, a transcricao ao vivo
   desce no fio da conversa e, com o pedido de ajuda, cada fala que cruza com
   os documentos do caso ganha logo abaixo a sugestao de resposta
   (POST /api/gravacoes/sugerir, src/sugestoes_ao_vivo.py: regra antes,
   modelo so quando a busca acha trecho, resposta ancorada no trecho).

   A coluna da direita vira a da gravacao (420 px): o gravador (Pausar,
   Marcar, Parar e arquivar), o contexto do caso (os documentos, com quantas
   sugestoes citaram cada um, e os pontos do caso) e os marcadores, com a
   chave "Sugerir respostas enquanto ouco". Parar e arquivar guarda a
   gravacao em Gravacoes e registra na conversa; a coluna volta ao contexto.

   O que nao existe e nao aparece: separar quem falou (diarizacao) - as falas
   vem sem nome de quem disse.
*/

const gcv = {
  ativa: false, trabalhoId: "", proposta: null, documentos: [], sugerir: false, sugestoes: [], citacoes: {},
  pontos: "", fila: [], pedindo: false, falas: [], voz: "",
};

function gravandoNestaConversa() {
  return gcv.ativa && estado.trabalhoId && estado.trabalhoId === gcv.trabalhoId;
}

async function gravarReuniaoNaConversa(d, caixa) {
  const v = gv.vivo;
  if (gcv.ativa || v.estado !== "pronto") {
    avisoCert("já há uma gravação andando", { acao: { rotulo: "Abrir", fazer: () => abrirGravacaoDaConversa() } });
    return;
  }
  const c = d.campos || {};
  Object.assign(gcv, {
    ativa: true, trabalhoId: estado.trabalhoId, proposta: d, documentos: c.documentos || [],
    sugerir: Boolean(c.ajudar && (c.documentos || []).length), sugestoes: [], citacoes: {}, pontos: "", fila: [], pedindo: false, falas: [],
  });
  if (!gv.tipos.length) {
    try { const t = await (await fetch("/api/gravacoes")).json(); gv.tipos = t.tipos || []; gv.clientes = t.clientes || []; } catch (err) { /* o titulo basta */ }
  }
  try { const voz = await (await fetch("/api/voz")).json(); gcv.voz = voz && voz.rotulo ? voz.rotulo : ""; } catch (err) { gcv.voz = ""; }
  v.form = { titulo: c.titulo || "Reunião", tipo: c.tipo || "reuniao", cadastro_id: c.cadastro_id || null, servico_id: null, participantes: "" };
  await comecarGravacao();
  if (v.estado !== "gravando") {
    gcv.ativa = false;
    if (caixa) caixa.innerHTML = '<p class="explica">Não comecei a gravar: ' + esc(v.erro || "o microfone não abriu") + "</p>";
    return;
  }
  // A proxima pergunta le os documentos do caso (a pilula da caixa diz).
  if (gcv.documentos.length) definirFoco(gcv.documentos);
  montarGravacaoNaConversa();
  if (gcv.documentos.length) carregarPontosDoCaso();
}

/* A gravacao na tela da conversa: o cabecalho, o bloco da transcricao no
   fio e a coluna. Volta a ser montada quando a conversa e redesenhada. */
function montarGravacaoNaConversa() {
  if (!gravandoNestaConversa()) return;
  $("conversa-meta").innerHTML = '<span class="gcv-meta"><i class="agr-rec vivo"></i>gravando · transcrição ao vivo · fica nesta máquina</span>';
  let bloco = $("gcv-transcricao");
  if (!bloco) {
    bloco = document.createElement("div");
    bloco.id = "gcv-transcricao";
    bloco.className = "gcv-transcricao";
    $("centro").appendChild(bloco);
  }
  desenharTranscricaoNaConversa();
  abrirNoLado("formulario", { chave: "gravacao", html: painelDaGravacaoNaConversa(), ligar: ligarPainelDaGravacao });
  if (gv.vivo.estado === "gravando") animarEqualizadorVivo();
  $("pedido").placeholder = "Pergunte sobre o caso enquanto grava…";
  rolar();
}

function linhaDaFala(f, i) {
  const s = gcv.sugestoes.find((x) => x.indice === i);
  return '<div class="gcv-fala" data-gcv-fala="' + i + '"><span class="gcv-t">' + duracaoGv(f.inicio) + "</span>" +
    "<p>" + esc(f.texto) + "</p></div>" + (s ? cartaoDaSugestaoAoVivo(s) : "");
}

function cartaoDaSugestaoAoVivo(s) {
  const classe = "gcv-sug-tipo " + s.tipo;
  const fonte = s.fonte || {};
  return '<div class="gcv-sugestao" data-gcv-sug="' + s.indice + '"><div class="gcv-sug-cabeca">' +
    '<span class="' + classe + '">' + esc(s.rotulo) + '</span><span class="gcv-sug-base">' + esc(s.base) + "</span>" +
    '<span class="vazio-flex"></span>' +
    '<button type="button" class="botao-icone" data-gcv-copiar="' + s.indice + '" title="Copiar" aria-label="Copiar">' + ic("content_copy", 15) + "</button>" +
    '<button type="button" class="botao-icone" data-gcv-tirar="' + s.indice + '" title="Tirar" aria-label="Tirar">' + ic("close", 15) + "</button></div>" +
    '<p class="gcv-sug-texto">“' + esc(s.texto) + "”</p>" +
    '<span class="gcv-sug-fonte">' + ic("description", 14) + esc(fonte.documento || "") + (fonte.pagina ? " · p. " + fonte.pagina : "") + "</span></div>";
}

function desenharTranscricaoNaConversa() {
  const bloco = $("gcv-transcricao");
  if (!bloco) return;
  const v = gv.vivo;
  const falas = v.transcricao || [];
  const ouvindo = v.estado === "gravando"
    ? '<div class="gcv-fala ouvindo"><span class="gcv-t">' + duracaoGv(segundosGravados()) + '</span><p>' +
      (v.sessao ? "ouvindo…" : esc(v.avisoVivo || "sem transcrição ao vivo nesta máquina — a transcrição sai ao arquivar")) +
      ' <i class="agr-respira"></i></p></div>'
    : (v.estado === "pausada" ? '<div class="gcv-fala ouvindo"><span class="gcv-t">' + duracaoGv(segundosGravados()) + "</span><p>em pausa</p></div>" : "");
  bloco.innerHTML = '<div class="gcv-cabeca"><span class="gcv-kicker">Transcrição</span><i></i><span class="gcv-modelo">' +
    esc((gcv.voz || "modelo de voz local") + " · " + plural(falas.length, "trecho")) + "</span></div>" +
    falas.map(linhaDaFala).join("") + ouvindo;
  ligarSugestoesAoVivo(bloco);
}

function ligarSugestoesAoVivo(raiz) {
  raiz.querySelectorAll("[data-gcv-copiar]").forEach((b) => {
    b.onclick = () => {
      const s = gcv.sugestoes.find((x) => x.indice === Number(b.dataset.gcvCopiar));
      if (s && navigator.clipboard) navigator.clipboard.writeText(s.texto).then(() => avisoCert("sugestão copiada", { tom: "ok" }));
    };
  });
  raiz.querySelectorAll("[data-gcv-tirar]").forEach((b) => {
    b.onclick = () => {
      const i = Number(b.dataset.gcvTirar);
      const el = raiz.querySelector('[data-gcv-sug="' + i + '"]');
      const tirar = () => { gcv.sugestoes = gcv.sugestoes.filter((x) => x.indice !== i); desenharTranscricaoNaConversa(); };
      if (el && animacoesLigadas()) sairDoAr(el, { aoFim: tirar }); else tirar();
    };
  });
}

/* O que o gravador chama a cada trecho novo (js/11-gravacoes.js). */
function aoTrechoAoVivo(trechos) {
  if (!gcv.ativa) return;
  const v = gv.vivo;
  const comeco = v.transcricao.length - trechos.length;
  if (gcv.sugerir) {
    trechos.forEach((t, k) => {
      const i = comeco + k;
      const anteriores = v.transcricao.slice(Math.max(0, i - 2), i).map((x) => x.texto).join(" ");
      gcv.fila.push({ indice: i, texto: t.texto, anteriores: anteriores });
    });
    processarSugestoes();
  }
  if (!gravandoNestaConversa()) return;
  const perto = pertoDoFim();
  desenharTranscricaoNaConversa();
  if (perto) rolar();
}

/* Uma sugestao por vez: o modelo responde uma pergunta por vez, e a fala
   que chegou primeiro e respondida primeiro. */
async function processarSugestoes() {
  if (gcv.pedindo || !gcv.fila.length || !gcv.ativa) return;
  gcv.pedindo = true;
  const item = gcv.fila.shift();
  try {
    const r = await fetch("/api/gravacoes/sugerir", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto: item.texto, documentos: gcv.documentos, anteriores: item.anteriores }) });
    const d = r.ok ? await r.json() : null;
    if (d && d.sugestao && gcv.ativa) {
      gcv.sugestoes.push(Object.assign({ indice: item.indice }, d.sugestao));
      const doc = (d.sugestao.fonte || {}).documento;
      if (doc) gcv.citacoes[doc] = (gcv.citacoes[doc] || 0) + 1;
      if (gravandoNestaConversa()) {
        const perto = pertoDoFim();
        desenharTranscricaoNaConversa();
        const nova = document.querySelector('#gcv-transcricao [data-gcv-sug="' + item.indice + '"]');
        if (nova && animacoesLigadas()) entraConteudo(nova);
        if (perto) rolar();
        redesenharPainelDaGravacao();
      }
    }
  } catch (err) {
    /* sem sugestao para esta fala: a transcricao continua */
  } finally {
    gcv.pedindo = false;
    if (gcv.fila.length) processarSugestoes();
  }
}

async function carregarPontosDoCaso() {
  try {
    const r = await fetch("/api/gravacoes/pontos", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ documentos: gcv.documentos }) });
    const d = r.ok ? await r.json() : null;
    if (d && d.pontos && gcv.ativa) { gcv.pontos = d.pontos; redesenharPainelDaGravacao(); }
  } catch (err) { /* sem os pontos, a coluna mostra so os documentos */ }
}

/* --------------------------------------------------------- a coluna */

function painelDaGravacaoNaConversa() {
  const v = gv.vivo;
  const f = v.form;
  const tipo = (gv.tipos.find((t) => t.valor === f.tipo) || {}).rotulo || "Gravação";
  const nomes = String(f.participantes || "").split(",").map((x) => x.trim()).filter(Boolean);
  const estadoTexto = v.estado === "pausada" ? "Em pausa" : v.estado === "salvando" ? "Guardando…" : "Gravando";
  const salvando = v.estado === "salvando" ? " disabled" : "";
  const docs = gcv.documentos.map((n) => '<div class="gcv-doc">' + glifo(n) + '<span class="corta">' + esc(n) + "</span>" +
    '<small>' + (gcv.citacoes[n] ? plural(gcv.citacoes[n], "citação", "citações") : "–") + "</small></div>").join("");
  const marcas = v.marcadores.map((m, i) => '<div class="gcv-marca"><span class="gcv-t">' + duracaoGv(m.t) + "</span>" +
    '<input type="text" value="' + esc(m.texto) + '" placeholder="o que aconteceu aqui" data-gcv-marca="' + i + '"></div>').join("");
  const classe = "ag-toggle" + (gcv.sugerir ? " on" : "") + (gcv.documentos.length ? "" : " presa");
  return '<div class="gcv-lado">' +
    '<section class="gcv-gravador"><div class="gcv-gravador-cabeca"><span class="agr-grava"><i class="agr-rec' + (v.estado === "gravando" ? " vivo" : "") + '"></i>' + estadoTexto + "</span>" +
    '<span class="gcv-gravador-meta">' + esc(tipo + (nomes.length ? " · " + plural(nomes.length, "participante") : "")) + "</span>" +
    '<span class="agr-grava-tempo" data-gv-tempo-agora="1">' + duracaoGv(segundosGravados()) + "</span></div>" +
    '<canvas class="gcv-onda" data-gv-onda-vivo="1"></canvas>' +
    '<div class="agr-grava-acoes"><button class="agr-acao" data-gcv-acao="pausar"' + salvando + ">" + ic(v.estado === "pausada" ? "mic" : "pause", 15) +
    (v.estado === "pausada" ? "Continuar" : "Pausar") + "</button>" +
    '<button class="agr-acao" data-gcv-acao="marcar"' + salvando + ">" + ic("bookmark", 15) + "Marcar</button><span class=\"vazio-flex\"></span>" +
    '<button class="agr-cheio" data-gcv-acao="parar"' + salvando + "><i></i>Parar e arquivar</button></div></section>" +
    '<section class="gcv-bloco"><div class="gcv-bloco-cabeca"><b>Contexto do caso</b><small>só nesta máquina</small></div>' +
    (docs || '<p class="gcv-nada">Sem documentos do caso: anexe na conversa ou ligue os arquivos ao Serviço do cliente para eu cruzar com o que for dito.</p>') +
    (gcv.pontos ? '<div class="gcv-pontos"><b>Pontos do caso</b><span>' + esc(gcv.pontos) + "</span></div>" : "") + "</section>" +
    '<section class="gcv-bloco cresce"><div class="gcv-bloco-cabeca"><b>Marcadores</b><small>' + v.marcadores.length + "</small></div>" +
    (marcas || '<p class="gcv-nada">Marque o minuto que importa e escreva o que aconteceu.</p>') +
    '<div class="gcv-chave"><span><b>Sugerir respostas enquanto ouço</b><small>' +
    (gcv.documentos.length ? "refutações e pedidos com base no caso" : "precisa dos documentos do caso") + "</small></span>" +
    '<button type="button" class="' + classe + '" data-gcv-sugerir="1" aria-label="Sugerir respostas enquanto ouço"><i></i></button></div></section></div>';
}

function ligarPainelDaGravacao(raiz) {
  raiz.querySelectorAll("[data-gcv-acao]").forEach((b) => {
    b.onclick = () => {
      const o = b.dataset.gcvAcao;
      if (o === "pausar") { pausarGravacao(); redesenharPainelDaGravacao(); desenharTranscricaoNaConversa(); }
      else if (o === "marcar") { marcarMomentoAoVivo(); redesenharPainelDaGravacao(); const c = [...raiz.querySelectorAll("[data-gcv-marca]")].pop(); if (c) c.focus(); }
      else if (o === "parar") pararGravacao();
    };
  });
  raiz.querySelectorAll("[data-gcv-marca]").forEach((c) => {
    c.oninput = () => { const m = gv.vivo.marcadores[Number(c.dataset.gcvMarca)]; if (m) m.texto = c.value; };
  });
  const chave = raiz.querySelector("[data-gcv-sugerir]");
  if (chave) chave.onclick = () => {
    if (!gcv.documentos.length) return;
    gcv.sugerir = !gcv.sugerir;
    if (!gcv.sugerir) gcv.fila = [];
    redesenharPainelDaGravacao();
  };
  if (gv.vivo.estado === "gravando") animarEqualizadorVivo();
  else { const tela = raiz.querySelector("[data-gv-onda-vivo]"); if (tela) desenharOnda(tela, null, false); }
}

function redesenharPainelDaGravacao() {
  if (!gravandoNestaConversa() || papelDoLado() !== "formulario" || lado.chave !== "gravacao") return;
  const ferramenta = $("lado-ferramenta");
  const ativo = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.gcvMarca : undefined;
  ferramenta.innerHTML = painelDaGravacaoNaConversa();
  ligarPainelDaGravacao(ferramenta);
  if (ativo !== undefined) { const c = ferramenta.querySelector('[data-gcv-marca="' + ativo + '"]'); if (c) { c.focus(); c.setSelectionRange(c.value.length, c.value.length); } }
}

function abrirGravacaoDaConversa() {
  if (gcv.ativa && gcv.trabalhoId) { abrirTrabalho(gcv.trabalhoId); return; }
  marcarDestino("gravacoes");
  mostrarGravacoes("vivo");
}

/* Parar e arquivar (js/11-gravacoes.js chama depois de guardar o audio): a
   gravacao entra na conversa como nota, com o caminho para ela, e a coluna
   volta ao contexto. Devolve true quando a gravacao era desta conversa. */
async function aoArquivarGravacao(g) {
  if (!gcv.ativa) return false;
  const id = gcv.trabalhoId;
  const sugeridas = gcv.sugestoes.length;
  gcv.ativa = false;
  gcv.fila = [];
  try {
    const r = await fetch("/api/trabalhos/" + id + "/fazer", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: "gravacao", campos: { id: g.id, sugestoes: sugeridas } }) });
    const feito = r.ok ? await r.json() : null;
    if (feito && estado.trabalhoId === id) {
      const nota = document.createElement("div");
      nota.className = "resposta nota-feito";
      nota.innerHTML = '<div class="texto">' + esc(feito.resumo + ".") + '</div><div class="gcv-abrir"><button type="button" class="avp-acao" data-gcv-abrir="' + g.id + '">Abrir a gravação</button></div>';
      $("centro").appendChild(nota);
      nota.querySelector("[data-gcv-abrir]").onclick = () => { gv.aberta = g; gv.aba = "transcricao"; marcarDestino("gravacoes"); mostrarGravacoes("gravacao"); };
      if (animacoesLigadas()) entraConteudo(nota);
      rolar();
    }
  } catch (err) { /* a gravacao ja esta em Gravacoes */ }
  if (estado.trabalhoId === id) {
    const bloco = $("gcv-transcricao");
    if (bloco) { desenharTranscricaoNaConversa(); bloco.classList.add("arquivada"); }
    voltarAoContexto();
    $("pedido").placeholder = "Pergunte outra coisa ou aponte outra pasta…";
    if (estado.trabalho) $("conversa-meta").textContent = "";
  }
  avisoCert("gravação arquivada em Gravações", { tom: "ok" });
  if (typeof carregarAgora === "function") carregarAgora();
  return true;
}

/* O relogio da transcricao (a linha "ouvindo") anda com o gravador. */
setInterval(() => {
  if (!gravandoNestaConversa()) return;
  const t = document.querySelector("#gcv-transcricao .gcv-fala.ouvindo .gcv-t");
  if (t) t.textContent = duracaoGv(segundosGravados());
}, 1000);
