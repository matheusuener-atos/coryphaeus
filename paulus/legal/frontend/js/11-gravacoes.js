/* ---------------------------------------------------------- gravacoes */
/*
   Gravacoes (docs/ui/03-telas-desktop.md, A16): a lista, o gravador ao vivo
   e a gravacao arquivada. O audio vem do microfone (MediaRecorder) ou de
   um arquivo importado e fica nesta maquina (src/gravacoes.py). Transcricao
   por falante, resumo e contexto ao vivo precisam de um modelo de voz local
   que ainda nao esta aqui: a tela mostra o lugar deles e diz isso, em vez
   de fingir uma transcricao. A gravacao vive fora do DOM (gv.vivo): trocar
   de tela nao a interrompe, e a lista mostra "gravando · ao vivo".
*/

const GV_JSON = { "Content-Type": "application/json" };
const GV_PLURAIS = { reuniao: "Reuniões", atendimento: "Atendimentos", audiencia: "Audiências", nota: "Notas de voz" };
const GV_VELOCIDADES = [1, 1.25, 1.5, 2];

const gv = {
  visao: "lista", tipo: "", termo: "", lista: [], totalSegundos: 0, tipos: [], clientes: [], servicos: [], pasta: "",
  aberta: null, aba: "transcricao", velocidade: 1, marcarTexto: "", voz: null, relogioVoz: null, buscaTrecho: "", resumindo: false,
  escolhidas: new Set(),
  // O tocador da lista: um só áudio, fora da página, a gravação que está nele
  // e a forma da onda de cada uma, lida uma vez.
  // O tocador na linha: um só áudio, fora da página; a gravação que está nele,
  // a linha aberta e as gravações que as linhas desenharam (a lista ou a
  // pasta de um serviço).
  som: null, tocandoId: null, expandida: null, naLinha: {},
  vivo: {
    estado: "pronto", inicio: 0, decorrido: 0, relogio: null, gravador: null, pedacos: [], fluxo: null, marcadores: [], erro: "",
    form: { titulo: "", tipo: "reuniao", cadastro_id: null, servico_id: null, participantes: "" },
    sessao: "", captura: null, amostras: [], enviando: false, relogioEnvio: null, enviados: 0, transcricao: [], rolar: true, avisoVivo: "",
  },
};

async function mostrarGravacoes(visao) {
  if (visao) gv.visao = visao;
  clearTimeout(gv.relogioVoz);
  if (gv.visao === "gravacao" && !gv.aberta) gv.visao = "lista";
  abrirTela("Gravações", { cheia: true });
  marcarDestino("gravacoes");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  atualizarPostura();
  try {
    const pedidos = [
      fetch("/api/gravacoes?termo=" + encodeURIComponent(gv.termo)).then((r) => r.json()),
      fetch("/api/voz").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ];
    if (gv.visao === "gravacao") pedidos.push(fetch("/api/gravacoes/" + gv.aberta.id).then((r) => (r.ok ? r.json() : null)));
    const [d, voz, g] = await Promise.all(pedidos);
    gv.voz = voz;
    gv.lista = d.gravacoes || [];
    gv.totalSegundos = d.total_segundos || 0;
    gv.tipos = d.tipos || [];
    gv.clientes = d.clientes || [];
    gv.pessoas = d.pessoas || [];
    gv.servicos = d.servicos || [];
    gv.pasta = d.pasta || "";
    if (gv.visao === "gravacao") {
      if (g) gv.aberta = g;
      else { gv.aberta = null; gv.visao = "lista"; avisoCert("essa gravação não existe mais"); }
    }
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharGravacoes();
}

async function abrirGravacao(id) {
  gv.aberta = { id: id };
  gv.aba = "transcricao";
  await mostrarGravacoes("gravacao");
}

function desenharGravacoes() {
  cabecalhoGravacoes();
  let html;
  if (gv.visao === "vivo") html = '<div class="acervo gv-tela" id="gv-tela">' + corpoAoVivo() + painelAoVivo() + "</div>";
  else if (gv.visao === "gravacao") html = '<div class="acervo gv-tela" id="gv-tela">' + corpoDaGravacao() + painelDaGravacao() + "</div>";
  else html = '<div class="acervo gv-tela sem-painel" id="gv-tela">' + corpoDaListaGv() + "</div>";
  $("centro").innerHTML = html;
  ligarGravacoes();
  atualizarPostura();
  vigiarVoz();
  if (gv.visao === "vivo" || gv.visao === "lista") animarEqualizadorVivo();
}

/* ------------------------------------------------------------ tempo */

function duracaoGv(segundos) {
  const s = Math.max(0, Math.round(segundos || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const dois = (n) => String(n).padStart(2, "0");
  return h ? h + ":" + dois(m) + ":" + dois(r) : m + ":" + dois(r);
}

function duracaoLongaGv(segundos) {
  const s = Math.max(0, Math.round(segundos || 0));
  const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
  if (h) return h + " h " + m + " min";
  if (m) return m + " min";
  return s + " s";
}

function segundosGravados() {
  const v = gv.vivo;
  return (v.decorrido + (v.estado === "gravando" ? Date.now() - v.inicio : 0)) / 1000;
}

function quandoDaGravacao(g) {
  const d = new Date(g.criado_em);
  if (isNaN(d)) return "";
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const dias = -diasAte(g.criado_em.slice(0, 10));
  if (dias === 0) return "hoje " + hora;
  if (dias === 1) return "ontem " + hora;
  return d.getDate() + " " + MESES_CURTOS[d.getMonth()] + (d.getFullYear() !== new Date().getFullYear() ? " " + d.getFullYear() : "") + " " + hora;
}

function tituloPadraoGv(form) {
  const rotulo = (gv.tipos.find((t) => t.valor === form.tipo) || {}).rotulo || "Gravação";
  const d = new Date();
  return rotulo + " · " + d.getDate() + " " + MESES_CURTOS[d.getMonth()] + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/* ------------------------------------------------------ o cabecalho */

function cabecalhoGravacoes() {
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  const nav = $("nav-tela");
  const botao = (v, r) => {
    const classe = v === gv.aba ? "ativa" : "";
    return '<button class="' + classe + '" data-gv-aba="' + v + '">' + r + "</button>";
  };
  const voltar = '<button class="voltar" data-gv-voltar="1" title="Voltar à lista" aria-label="Voltar à lista">' + ic("arrow_back", 18) + "</button>";
  if (gv.visao === "vivo") {
    const v = gv.vivo;
    nav.innerHTML = voltar;
    titulo.textContent = v.estado === "pronto" ? "Nova gravação" : (v.form.titulo || tituloPadraoGv(v.form));
    meta.textContent = v.estado === "pronto" ? "microfone desta máquina · o áudio fica só aqui" : metaAoVivo();
    $("acoes-tela").innerHTML = "";
    return;
  }
  if (gv.visao === "gravacao" && gv.aberta) {
    const g = gv.aberta;
    nav.innerHTML = voltar;
    titulo.textContent = g.titulo;
    // O nome da gravação se renomeia clicando nele, como o de uma pasta.
    titulo.classList.add("renomeavel");
    titulo.title = "Clique para renomear";
    renomeadorDoTitulo = { limite: 120, guardar: (novo) => renomearGravacaoAberta(novo) };
    meta.textContent = [quandoDaGravacao(g), duracaoLongaGv(g.duracao_s), g.participantes_lista.join(", ")].filter(Boolean).join(" · ") +
      " · " + statusDaGravacao(g);
    $("acoes-tela").innerHTML =
      '<button class="com-icone" data-gv-compartilhar="1">' + ic("mail", 16) + "Compartilhar resumo</button>" +
      '<button class="primario com-icone" data-gv-perguntar="1">' + ic("forum", 16) + "Perguntar sobre esta gravação</button>";
    return;
  }
  nav.innerHTML = "";
  titulo.textContent = "Gravações";
  meta.textContent = plural(gv.lista.length, "gravação", "gravações") + " · reuniões, atendimentos, audiências e notas de voz · o áudio fica nesta máquina";
  $("acoes-tela").innerHTML =
    '<label class="busca-tela">' + ic("search", 18) + '<input type="text" id="gv-busca" placeholder="Buscar gravações…" value="' + esc(gv.termo) + '"></label>' +
    '<button class="primario com-icone" data-gv-nova="1">' + ic("mic", 16) + "Nova gravação</button>";
}

function metaAoVivo() {
  const v = gv.vivo;
  const servico = gv.servicos.find((s) => s.id === v.form.servico_id);
  return [servico ? "Serviço: " + servico.nome : "", (gv.tipos.find((t) => t.valor === v.form.tipo) || {}).rotulo,
    v.estado === "pausada" ? "pausada" : (v.estado === "salvando" ? "guardando" : "gravando")].filter(Boolean).join(" · ");
}

/* ----------------------------------------------------------- a lista */

function avataresGv(nomes, quantos) {
  const lista = nomes.slice(0, quantos || 3);
  const resto = nomes.length - lista.length;
  if (!lista.length) return '<span class="gv-avatares"><small>—</small></span>';
  return '<span class="gv-avatares">' + lista.map((n) => '<span class="cad-avatar" title="' + esc(n) + '">' + esc(iniciaisDoRemetente(n)) + "</span>").join("") +
    (resto > 0 ? "<small>+" + resto + "</small>" : "") + "</span>";
}

function linhaAoVivoGv() {
  const v = gv.vivo;
  if (v.estado === "pronto") return "";
  const nomes = v.form.participantes.split(",").map((x) => x.trim()).filter(Boolean);
  return '<div class="tabela-linha colunas-gravacoes" data-gv-vivo="1"><span class="gv-ic-linha viva">' + ic("mic", 20) + "</span>" +
    '<div class="duas-linhas"><b>' + esc(v.form.titulo || tituloPadraoGv(v.form)) + "</b><small>" + esc(metaAoVivo()) + "</small></div>" +
    avataresGv(nomes) + '<span class="gv-duracao" id="gv-tempo-linha">' + duracaoGv(segundosGravados()) + "</span>" +
    '<span class="fin-status gv-viva">' + (v.estado === "pausada" ? "pausada · ao vivo" : "gravando · ao vivo") + '</span><span></span></div>';
}

function corpoDaListaGv() {
  const lista = gv.tipo ? gv.lista.filter((g) => g.tipo === gv.tipo) : gv.lista;
  const chips = [["", "Todas · " + gv.lista.length]].concat(gv.tipos.map((t) => [t.valor, GV_PLURAIS[t.valor] || t.rotulo])).map(([v, r]) => {
    const classe = v === gv.tipo ? "on" : "";
    return '<button class="' + classe + '" data-gv-tipo="' + v + '">' + r + "</button>";
  }).join("");
  const linhas = lista.map((g) => {
    const sub = [quandoDaGravacao(g), g.servico_nome ? "Serviço: " + g.servico_nome : "", !g.servico_nome && g.cliente_nome ? g.cliente_nome : ""].filter(Boolean).join(" · ");
    const status = statusDaGravacao(g);
    const aberta = gv.expandida === g.id;
    const classe = "tabela-linha colunas-gravacoes" + (gv.escolhidas.has(String(g.id)) ? " escolhida" : "") + (aberta ? " aberta" : "");
    return '<div class="' + classe + '" data-gv-expandir="' + g.id + '" data-sel="' + g.id + '" title="Clique para ouvir · duplo clique abre">' + iconeDaLinhaGv(g) +
      '<div class="duas-linhas"><b>' + esc(g.titulo) + "</b><small>" + esc(sub) + "</small></div>" + avataresGv(g.participantes_lista) +
      '<span class="gv-duracao">' + duracaoGv(g.duracao_s) + '</span><span class="fin-status">' + status + "</span>" +
      '<button class="mais-linha" data-gv-mais="' + g.id + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>" +
      (aberta ? tocadorNaLinhaGv(g) : "");
  }).join("");
  let vazio = "";
  if (!linhas && !linhaAoVivoGv()) {
    vazio = '<p class="rel-vazio">' + (gv.termo ? "Nada com “" + esc(gv.termo) + "”. Procurei no título, nos participantes, nas notas, no cliente e no serviço." :
      (gv.tipo ? "Nenhuma gravação deste tipo." : "Nenhuma gravação ainda. Grave pelo microfone em Nova gravação ou importe um áudio — tudo fica nesta máquina, e a transcrição entra quando houver um modelo de voz local.")) + "</p>";
  }
  const barra = gv.escolhidas.size
    ? barraDeSelecao(gv.escolhidas.size, true, '<button class="botao-icone perigo" data-gv-sel-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-gv-sel-limpar")
    : '<div class="ag-chips">' + chips + "</div>";
  return '<div class="acervo-principal">' + cartaoDoGravadorGv(true) + '<div class="tabela-cartao gv-lista">' +
    '<div class="tabela-barra">' + barra +
    '<div class="direita"><input type="file" id="gv-importar" hidden accept="audio/*,.webm,.ogg,.opus,.mp3,.m4a,.wav,.aac,.flac,.mp4">' +
    '<button data-gv-importar="1">' + ic("upload", 16) + "Importar áudio</button></div></div>" +
    '<div class="tabela-cabecalho colunas-gravacoes"><span></span><span>Gravação</span><span>Participantes</span><span>Duração</span><span>Status</span><span></span></div>' +
    '<div class="tabela-corpo">' + linhaAoVivoGv() + linhas + vazio + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + gv.lista.length + " · " + duracaoLongaGv(gv.totalSegundos) + ' gravados</span>' +
    '<span class="direita">' + esc(notaDaVoz()) + "</span></div></div></div>";
}

/* ------------------------------------------------ o tocador na linha */

/* O TOCADOR NA LINHA. Clicar numa gravação — na lista ou nos Arquivos de um
   serviço — abre a linha e mostra o tocador: tocar, o equalizador do ditado
   lendo o som, a barra com os marcadores (clica-se para ir a um ponto), o
   tempo, a velocidade e Abrir gravação. O áudio é um objeto só, fora da
   página: redesenhar não corta o som; fechar a linha, abrir outra ou sair da
   tela para. */
function somGv() {
  if (!gv.som) {
    const som = new Audio();
    som.preload = "metadata";
    som.onplay = som.onpause = som.onended = () => estadoDoSomGv();
    som.onerror = () => { if (som.getAttribute("src")) avisoCert("não consegui tocar o áudio — o formato pode não ser reconhecido por esta janela"); };
    gv.som = som;
  }
  return gv.som;
}

function totalDoSomGv() {
  const som = gv.som;
  const g = gv.naLinha[gv.tocandoId];
  return som && isFinite(som.duration) && som.duration ? som.duration : (g ? g.duracao_s : 0);
}

function tocandoAgoraGv(id) {
  return Boolean(gv.som && gv.tocandoId === id && !gv.som.paused && !gv.som.ended);
}

function iconeDaLinhaGv(g) {
  const tocando = tocandoAgoraGv(g.id);
  const classe = "gv-ic-linha" + (tocando ? " tocando" : "");
  return '<span class="' + classe + '" data-gv-icone="' + g.id + '">' +
    (tocando ? '<span class="gv-eq"><i></i><i></i><i></i><i></i></span>' : ic("graphic_eq", 20)) + "</span>";
}

function tocadorNaLinhaGv(g) {
  gv.naLinha[g.id] = g;
  if (!g.existe) return '<div class="gv-linha-tocador"><span class="nota-barra">o áudio desta gravação não está mais no disco</span></div>';
  const deste = Boolean(gv.som && gv.tocandoId === g.id);
  const tocando = tocandoAgoraGv(g.id);
  const total = deste ? totalDoSomGv() : g.duracao_s;
  const agora = deste ? gv.som.currentTime : 0;
  const marcas = (g.marcadores || []).map((m) => '<u style="left:' + porcentagemGv(m.t, total) + '%" title="' + esc(m.texto || duracaoGv(m.t)) + '"></u>').join("");
  return '<div class="gv-linha-tocador" data-gv-linha-tocador="' + g.id + '">' +
    '<button class="gv-radio-tocar" data-gv-lt-tocar="1" title="' + (tocando ? "Pausar" : "Tocar") + '" aria-label="' + (tocando ? "Pausar" : "Tocar") + '">' +
    ic(tocando ? "pause" : "play_arrow", 22) + "</button>" +
    '<div class="gv-lt-meio"><canvas class="ditado-onda gv-lt-onda" data-gv-lt-onda="1"></canvas>' +
    '<div class="gv-barra" data-gv-lt-barra="1" title="Clique para ir a este ponto"><i data-gv-lt-fill="1" style="width:' + porcentagemGv(agora, total) + '%"></i>' + marcas + "</div></div>" +
    '<span class="ditado-tempo gv-lt-tempo"><span data-gv-lt-pos="1">' + duracaoGv(agora) + "</span> / " + duracaoGv(total) + "</span>" +
    '<button class="fantasma gv-vel" data-gv-lt-vel="1" title="Velocidade">' + velocidadeGv() + "</button>" +
    '<button class="com-icone" data-gv-lt-abrir="' + g.id + '">' + ic("open_in_new", 16) + "Abrir gravação</button></div>";
}

/* O equalizador do tocador na linha lê o próprio áudio. O contexto nasce no
   primeiro Tocar (a janela só deixa depois de um clique) e o áudio só pode
   ser ligado a um contexto uma vez — por isso o áudio é um só. */
function equalizadorDoSomGv() {
  if (gv.somAnalisador) {
    if (gv.somContexto.state === "suspended") gv.somContexto.resume().catch(() => {});
    return;
  }
  const Contexto = window.AudioContext || window.webkitAudioContext;
  if (!Contexto) return;
  try {
    const contexto = new Contexto();
    const analisador = contexto.createAnalyser();
    analisador.fftSize = 256;
    analisador.smoothingTimeConstant = 0.72;
    contexto.createMediaElementSource(gv.som).connect(analisador);
    analisador.connect(contexto.destination);
    gv.somContexto = contexto;
    gv.somAnalisador = analisador;
  } catch (err) { /* sem equalizador; o som toca do mesmo jeito */ }
}

function tocarNaLinhaGv(g, fracao) {
  const som = somGv();
  equalizadorDoSomGv();
  if (gv.tocandoId !== g.id || !som.getAttribute("src")) {
    gv.tocandoId = g.id;
    gv.naLinha[g.id] = g;
    som.src = "/api/gravacoes/" + g.id + "/audio";
    som.playbackRate = gv.velocidade;
    if (fracao !== undefined) som.onloadedmetadata = () => { som.onloadedmetadata = null; som.currentTime = fracao * totalDoSomGv(); };
    som.play().catch(() => {});
    return;
  }
  if (fracao !== undefined) {
    som.currentTime = fracao * totalDoSomGv();
    if (som.paused) som.play().catch(() => {});
    animarLinhaGv();
    return;
  }
  if (som.paused || som.ended) som.play().catch(() => {});
  else som.pause();
}

function estadoDoSomGv() {
  document.querySelectorAll("[data-gv-icone]").forEach((el) => { el.outerHTML = iconeDaLinhaGv({ id: Number(el.dataset.gvIcone) }); });
  const caixa = document.querySelector('[data-gv-linha-tocador="' + gv.tocandoId + '"]');
  if (caixa) {
    const tocando = tocandoAgoraGv(gv.tocandoId);
    const botao = caixa.querySelector("[data-gv-lt-tocar]");
    botao.innerHTML = ic(tocando ? "pause" : "play_arrow", 22);
    botao.title = tocando ? "Pausar" : "Tocar";
    caixa.classList.toggle("tocando", tocando);
  }
  animarLinhaGv();
}

/* O quadro do tocador: o equalizador, a barra e o tempo. Sem a linha dele
   na página, o som para. */
function animarLinhaGv() {
  cancelAnimationFrame(gv.quadroLinha || 0);
  gv.quadroLinha = 0;
  const som = gv.som;
  if (!som || !som.getAttribute("src")) return;
  const caixa = document.querySelector('[data-gv-linha-tocador="' + gv.tocandoId + '"]');
  if (!caixa) { if (!som.paused) som.pause(); return; }
  const tocando = !som.paused && !som.ended;
  let dados = null;
  if (tocando && gv.somAnalisador) {
    dados = new Uint8Array(gv.somAnalisador.frequencyBinCount);
    gv.somAnalisador.getByteFrequencyData(dados);
  }
  const tela = caixa.querySelector("[data-gv-lt-onda]");
  if (tela) desenharOnda(tela, dados, tocando);
  const total = totalDoSomGv();
  const fill = caixa.querySelector("[data-gv-lt-fill]");
  if (fill) fill.style.width = porcentagemGv(som.currentTime, total) + "%";
  const pos = caixa.querySelector("[data-gv-lt-pos]");
  if (pos) pos.textContent = duracaoGv(som.currentTime);
  if (tocando) gv.quadroLinha = requestAnimationFrame(animarLinhaGv);
}

/* Liga o tocador que estiver na página, qualquer que seja a tela. */
function ligarTocadorNaLinhaGv() {
  const caixa = document.querySelector("[data-gv-linha-tocador]");
  if (!caixa) { animarLinhaGv(); return; }
  const id = Number(caixa.dataset.gvLinhaTocador);
  const g = gv.naLinha[id];
  if (!g) return;
  caixa.onclick = (e) => e.stopPropagation();
  caixa.querySelector("[data-gv-lt-tocar]").onclick = () => tocarNaLinhaGv(g);
  const barra = caixa.querySelector("[data-gv-lt-barra]");
  barra.onclick = (e) => {
    const r = barra.getBoundingClientRect();
    tocarNaLinhaGv(g, Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)));
  };
  caixa.querySelector("[data-gv-lt-vel]").onclick = (e) => {
    const i = GV_VELOCIDADES.indexOf(gv.velocidade);
    gv.velocidade = GV_VELOCIDADES[(i + 1) % GV_VELOCIDADES.length];
    if (gv.som) gv.som.playbackRate = gv.velocidade;
    e.currentTarget.textContent = velocidadeGv();
  };
  caixa.querySelector("[data-gv-lt-abrir]").onclick = () => abrirGravacao(id);
  const tela = caixa.querySelector("[data-gv-lt-onda]");
  if (gv.tocandoId === id) animarLinhaGv();
  else {
    animarLinhaGv();
    if (tela) desenharOnda(tela, null, false);
  }
}

/* Trocar de tela para o som - menos voltar à própria lista (a busca, que
   redesenha tudo, não corta o som). */
function pararTocadorDaListaGv(tela) {
  if (!gv.som || gv.som.paused) return;
  if (tela === "Gravações" && gv.visao === "lista") return;
  gv.som.pause();
}

/* ---------------------------------------------------------- ao vivo */

function corpoAoVivo() {
  return '<div class="acervo-principal gv-vivo">' + cartaoDosDetalhesGv() + cartaoDoGravadorGv() + cartaoAoVivo() + "</div>";
}

/* O GRAVADOR É O CARTÃO DO DITADO DA CONVERSA: o estado e o tempo em cima,
   o equalizador do microfone no meio (em pausa, as barras deitam), uma
   linha de rodapé e as ações embaixo — Começar a gravar, e depois Pausar,
   Marcar momento e Parar e arquivar. */
function cartaoDoGravadorGv(naLista) {
  const v = gv.vivo;
  const nomes = { pronto: "Pronto para gravar", gravando: "Gravando", pausada: "Gravação em pausa", salvando: "Guardando o áudio…" };
  const salvando = v.estado === "salvando";
  const botao = (dado, icone, rotulo, classe) => '<button class="' + (classe || "fantasma") + '" ' + dado + '="1"' + (salvando ? " disabled" : "") + ">" +
    ic(icone, 16) + rotulo + "</button>";
  // Na lista, o cartão é a gravação rápida: começa ali mesmo, e Abrir
  // gravação leva à tela inteira (detalhes, transcrição ao vivo, painel).
  const abrir = naLista ? botao("data-gv-vivo", "open_in_new", "Abrir gravação") : "";
  const acoes = v.estado === "pronto"
    ? '<span class="gv-vivo-dica">Avise os participantes de que a conversa está sendo gravada.</span>' + abrir + botao("data-gv-comecar", "mic", "Começar a gravar", "primario")
    : botao("data-gv-pausar", v.estado === "pausada" ? "play_arrow" : "pause", v.estado === "pausada" ? "Continuar" : "Pausar") +
      botao("data-gv-marcar-vivo", "bookmark_add", "Marcar momento") + abrir +
      botao("data-gv-parar", "stop_circle", "Parar e arquivar", "primario");
  const modo = { pronto: "pronto", gravando: "ouvindo", pausada: "pausado", salvando: "finalizando" }[v.estado];
  const classe = "cartao-agora ditado-cartao gv-vivo-cartao " + modo;
  return '<div class="' + classe + '">' +
    '<div class="cabeca">' + (salvando ? coroa(20) : ic("mic", 20)) + '<span class="nome">' + nomes[v.estado] + "</span>" +
    '<span class="ditado-tempo" id="gv-tempo">' + duracaoGv(segundosGravados()) + "</span></div>" +
    '<canvas class="ditado-onda" data-gv-onda-vivo="1"></canvas>' +
    (v.erro ? '<div class="gv-erro">' + esc(v.erro) + "</div>" : "") +
    (v.estado === "pronto" ? "" : '<div class="rodape" id="gv-vivo-rodape">' + esc(rodapeDoGravadorGv()) + "</div>") +
    '<div class="acoes">' + acoes + "</div></div>";
}

function rodapeDoGravadorGv() {
  const v = gv.vivo;
  if (v.estado === "pronto") return "microfone desta máquina · o áudio fica só aqui";
  return (v.form.titulo || tituloPadraoGv(v.form)) + " · " + plural(v.marcadores.length, "marcador", "marcadores") + " · trocar de tela não interrompe a gravação";
}

/* O que se sabe da gravação, num cartão à parte. Vale mudar durante a
   gravação: tudo entra no arquivo ao parar e arquivar. */
function cartaoDosDetalhesGv() {
  const f = gv.vivo.form;
  const tipos = gv.tipos.map((t) => { const classe = t.valor === f.tipo ? "on" : ""; return '<button type="button" class="' + classe + '" data-gv-form-tipo="' + t.valor + '">' + esc(t.rotulo) + "</button>"; }).join("");
  const clientes = '<option value="">sem cliente</option>' + gv.clientes.map((c) => '<option value="' + c.id + '"' + (c.id === f.cadastro_id ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("");
  const servicos = '<option value="">sem serviço</option>' + gv.servicos.map((x) => '<option value="' + x.id + '"' + (x.id === f.servico_id ? " selected" : "") + ">" + esc(x.nome) + "</option>").join("");
  return '<div class="fin-cartao gv-detalhes"><div class="fin-cartao-cabeca"><span>Detalhes da gravação</span><small>entram no arquivo ao parar e arquivar</small></div>' +
    '<div class="gv-forma">' +
    '<div class="ag-campo"><label>Título</label><input type="text" data-gv-form="titulo" value="' + esc(f.titulo) + '" placeholder="' + esc(tituloPadraoGv(f)) + '"></div>' +
    '<div class="ag-campo gv-participantes"><label>Participantes</label><input type="text" data-gv-form="participantes" data-gv-participantes="1" value="' + esc(f.participantes) + '" placeholder="Priscila Almeida, João Medeiros" autocomplete="off">' +
    '<div class="mencao gv-sugestoes" data-gv-sugestoes="1" hidden></div></div>' +
    '<div class="ag-campo gv-forma-inteira"><label>Tipo</label><div class="ag-chips">' + tipos + "</div></div>" +
    '<div class="ag-campo"><label>Cliente</label><select data-gv-form="cadastro_id">' + clientes + "</select></div>" +
    '<div class="ag-campo"><label>Serviço</label><select data-gv-form="servico_id">' + servicos + "</select></div>" +
    "</div></div>";
}

/* O painel do ao vivo: os marcadores primeiro (é o que se usa gravando), o
   contexto e a sugestão de respostas. */
function painelAoVivo() {
  const v = gv.vivo;
  const gravando = v.estado === "gravando" || v.estado === "pausada";
  const marcadores = v.marcadores.map((m, i) => '<div class="gv-marcador">' + ic("bookmark", 18) + '<span class="em-ligacao forte">' + duracaoGv(m.t) + "</span>" +
    '<input type="text" value="' + esc(m.texto) + '" placeholder="o que aconteceu aqui" data-gv-marcador-vivo="' + i + '">' +
    '<button class="mais-linha" data-gv-marcador-vivo-tirar="' + i + '" title="Tirar">' + ic("close", 16) + "</button></div>").join("");
  return '<aside class="acervo-painel gv-painel"><div class="rolagem">' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca">Marcadores' +
    (gravando ? '<button class="em-ligacao forte" data-gv-marcar-vivo="1">+ marcar agora</button>' : '<span class="contagem">' + v.marcadores.length + "</span>") + "</div>" +
    (marcadores || '<p class="nota">' + (gravando ? "Nenhum marcador ainda. Marque o minuto que importa e escreva o que aconteceu." : "Durante a gravação, Marcar momento guarda o minuto — e você escreve o que aconteceu.") + "</p>") + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca">Contexto ao vivo<span class="contagem">só nesta máquina</span></div>' +
    '<p class="nota">Com a transcrição, o assistente vai cruzar o que é dito com os arquivos do serviço e o Acervo — a cláusula citada, o valor em atraso, o prazo que muda. Até lá, este espaço não inventa contexto.</p></div>' +
    '<div class="painel-bloco">' + ligaCfg("", "Sugerir respostas enquanto ouço", "com base nos arquivos do serviço e no Acervo · entra com a transcrição", false, true) + "</div>" +
    "</div></aside>";
}

/* PARTICIPANTES COMO O "/" DA CONVERSA. O campo sugere os nomes que o
   programa conhece (Cadastros e quem já participou de outra gravação),
   filtrando pelo nome que está sendo escrito depois da última vírgula; setas
   andam, Enter ou Tab escolhem, Esc fecha. Sem nome que combine, o campo só
   recebe o que se digita. */
function ligarParticipantesGv() {
  const campo = document.querySelector("[data-gv-participantes]");
  const caixa = document.querySelector("[data-gv-sugestoes]");
  if (!campo || !caixa) return;
  const plano = (t) => String(t || "").normalize("NFD").replace(new RegExp("[\u0300-\u036f]", "g"), "").toLowerCase();
  let itens = [];
  let marcado = 0;
  const fechar = () => { caixa.hidden = true; caixa.innerHTML = ""; itens = []; };
  const pedaco = () => {
    const ate = campo.value.slice(0, campo.selectionStart);
    const inicio = ate.lastIndexOf(",") + 1;
    return { inicio: inicio, termo: ate.slice(inicio).trim() };
  };
  const abrir = () => {
    const { termo } = pedaco();
    const ja = new Set(campo.value.split(",").map((n) => plano(n.trim())).filter(Boolean));
    // Cada palavra digitada precisa estar no nome, em qualquer ordem: "teste pri" acha "Priscila Teste".
    const partes = plano(termo).split(/\s+/).filter(Boolean);
    itens = (gv.pessoas || []).filter((p) => !ja.has(plano(p.nome)) && partes.every((x) => plano(p.nome).includes(x))).slice(0, 8);
    if (!itens.length) { fechar(); return; }
    marcado = 0;
    caixa.hidden = false;
    caixa.innerHTML = itens.map((p, i) => {
      const classe = "mencao-item" + (i === 0 ? " marcado" : "");
      return '<button type="button" class="' + classe + '" data-gv-pessoa="' + i + '"><b>' + esc(p.nome) + "</b>" +
        (p.detalhe ? '<span class="rotulo">' + esc(p.detalhe) + "</span>" : "") + "</button>";
    }).join("");
    caixa.querySelectorAll("[data-gv-pessoa]").forEach((b) => {
      b.onmousedown = (e) => { e.preventDefault(); escolher(itens[Number(b.dataset.gvPessoa)]); };
    });
  };
  const escolher = (p) => {
    const { inicio } = pedaco();
    const depois = campo.value.slice(campo.selectionStart).replace(/^[^,]*,?\s*/, "");
    const antes = campo.value.slice(0, inicio).replace(/\s*$/, "");
    campo.value = (antes ? antes + " " : "") + p.nome + ", " + depois;
    const fim = ((antes ? antes + " " : "") + p.nome + ", ").length;
    campo.setSelectionRange(fim, fim);
    gv.vivo.form.participantes = campo.value.replace(/,\s*$/, "");
    fechar();
    abrir();
  };
  const andar = (passo) => {
    marcado = (marcado + passo + itens.length) % itens.length;
    caixa.querySelectorAll(".mencao-item").forEach((b, i) => {
      b.classList.toggle("marcado", i === marcado);
      if (i === marcado) b.scrollIntoView({ block: "nearest" });
    });
  };
  campo.onfocus = abrir;
  campo.onclick = abrir;
  campo.addEventListener("input", () => {
    gv.vivo.form.participantes = campo.value;
    abrir();
  });
  campo.onkeydown = (e) => {
    if (caixa.hidden || !itens.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); andar(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); andar(-1); }
    else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); escolher(itens[marcado]); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fechar(); }
  };
  campo.onblur = () => {
    setTimeout(fechar, 120);
    gv.vivo.form.participantes = campo.value.replace(/,\s*$/, "").trim();
  };
}

/* O equalizador do gravador: o analisador lê o próprio microfone, num
   contexto de áudio só dele, e o desenho é o do ditado. */
function ligarEqualizadorVivo(fluxo) {
  const v = gv.vivo;
  pararEqualizadorVivo();
  const Contexto = window.AudioContext || window.webkitAudioContext;
  if (Contexto) {
    try {
      const contexto = new Contexto();
      const analisador = contexto.createAnalyser();
      analisador.fftSize = 256;
      analisador.smoothingTimeConstant = 0.7;
      contexto.createMediaStreamSource(fluxo).connect(analisador);
      v.equalizador = { contexto: contexto, analisador: analisador };
    } catch (err) {
      v.equalizador = null;
    }
  }
  animarEqualizadorVivo();
}

function animarEqualizadorVivo() {
  const v = gv.vivo;
  cancelAnimationFrame(v.quadroEq || 0);
  const tela = document.querySelector("[data-gv-onda-vivo]");
  const ouvindo = v.estado === "gravando";
  if (tela) {
    let dados = null;
    if (ouvindo && v.equalizador) {
      dados = new Uint8Array(v.equalizador.analisador.frequencyBinCount);
      v.equalizador.analisador.getByteFrequencyData(dados);
    }
    desenharOnda(tela, dados, ouvindo);
  }
  v.quadroEq = ouvindo ? requestAnimationFrame(animarEqualizadorVivo) : 0;
}

function pararEqualizadorVivo() {
  const v = gv.vivo;
  cancelAnimationFrame(v.quadroEq || 0);
  v.quadroEq = 0;
  if (v.equalizador) {
    try { v.equalizador.contexto.close(); } catch (err) { /* ja fechado */ }
    v.equalizador = null;
  }
}

/* --------------------------------------------------------- gravacao *//* --------------------------------------------------------- gravacao */

function corpoDaGravacao() {
  const g = gv.aberta;
  // O tocador tem a cara do cartão do ditado da conversa: o estado e o
  // tempo em cima, o equalizador espelhado no meio (a voz tocando, na cor de
  // destaque; em pausa, as barras deitam), a barra com os marcadores e as
  // ações embaixo.
  const player = g.existe
    ? '<div class="cartao-agora gv-player" id="gv-player"><audio id="gv-audio" src="/api/gravacoes/' + g.id + '/audio" preload="metadata"></audio>' +
      '<div class="cabeca">' + ic("graphic_eq", 20) + '<span class="nome" id="gv-player-nome">Pronto para ouvir</span>' +
      '<span class="ditado-tempo gv-posicao"><span id="gv-posicao">0:00</span> / ' + duracaoGv(g.duracao_s) + "</span></div>" +
      '<canvas class="ditado-onda" data-gv-onda-tocador="1"></canvas>' +
      '<div class="gv-barra" data-gv-barra="1"><i id="gv-barra-fill"></i>' + g.marcadores.map((m) => '<u style="left:' + porcentagemGv(m.t, g.duracao_s) + '%" title="' + esc(m.texto || duracaoGv(m.t)) + '"></u>').join("") + "</div>" +
      '<div class="acoes">' +
      '<button class="fantasma" data-gv-pular="-10" title="Voltar 10 s">' + ic("replay_10", 16) + "10 s</button>" +
      '<button class="fantasma" data-gv-pular="10" title="Avançar 10 s">' + ic("forward_10", 16) + "10 s</button>" +
      '<button class="fantasma gv-vel" data-gv-velocidade="1" title="Velocidade">' + velocidadeGv() + "</button>" +
      '<button class="primario" data-gv-tocar="1">' + ic("play_arrow", 16) + "Tocar</button></div></div>"
    : '<div class="cartao-agora gv-player"><div class="cabeca">' + ic("graphic_eq", 20) + '<span class="nome">Sem áudio</span>' +
      '<span class="ditado-tempo gv-posicao">— / ' + duracaoGv(g.duracao_s) + '</span></div><div class="rodape">o arquivo de áudio não está mais em ' + esc(gv.pasta) + "</div></div>";
  return '<div class="acervo-principal">' + player + '<div class="gv-conteudo" id="gv-conteudo">' + conteudoDaGravacao() + "</div></div>";
}

function porcentagemGv(t, total) {
  return total ? Math.min(100, Math.max(0, (t / total) * 100)).toFixed(1) : 0;
}

function velocidadeGv() {
  return String(gv.velocidade).replace(".", ",") + "×";
}

/* O CARTÃO CONTEÚDO: Transcrição, Resumo e Marcadores são abas à direita da
   barra dele; as ferramentas de cada aba vêm numa faixa logo abaixo. */
function conteudoDaGravacao() {
  const abas = [["transcricao", "Transcrição"], ["resumo", "Resumo"], ["marcadores", "Marcadores"]].map(([v, r]) => {
    const classe = v === gv.aba ? "ativa" : "";
    return '<button class="' + classe + '" data-gv-aba="' + v + '">' + r + "</button>";
  }).join("");
  return '<div class="fin-cartao gv-conteudo-cartao"><div class="fin-cartao-cabeca"><span>Conteúdo</span><div class="visoes gv-abas">' + abas + "</div></div>" +
    mioloDaGravacao() + "</div>";
}

function mioloDaGravacao() {
  const g = gv.aberta;
  if (gv.aba === "marcadores") {
    const linhas = g.marcadores.map((m, i) => '<div class="gv-marcador sv-evento grande">' + ic("bookmark", 18) +
      '<button class="em-ligacao forte" data-gv-ir="' + m.t + '">' + duracaoGv(m.t) + "</button>" +
      '<input type="text" value="' + esc(m.texto) + '" placeholder="o que aconteceu aqui" data-gv-marcador="' + i + '">' +
      '<button class="mais-linha" data-gv-marcador-tirar="' + i + '" title="Tirar">' + ic("close", 16) + "</button></div>").join("");
    return '<div class="gv-miolo gv-marcadores"><div class="gv-ferramentas"><small>' + plural(g.marcadores.length, "marcador", "marcadores") + "</small>" +
      '<div class="direita gv-marcar"><input type="text" placeholder="o que aconteceu neste momento" data-gv-marcar-texto="1" value="' + esc(gv.marcarTexto) + '">' +
      '<button data-gv-marcar="1"' + (g.existe ? "" : " disabled") + ">" + ic("bookmark_add", 16) + 'Marcar em <span id="gv-marcar-em">' + duracaoGv(posicaoDoAudio()) + "</span></button></div></div>" +
      '<div class="gv-miolo-corpo">' + (linhas || '<p class="nota">Nenhum marcador. Toque o áudio e marque os momentos que importam; o minuto fica clicável.</p>') + "</div></div>";
  }
  if (gv.aba === "resumo") return cartaoDoResumoGv(g);
  return cartaoDaTranscricao(g);
}

/* --------------------------------------------- transcricao e resumo */

function statusDaGravacao(g) {
  if (!g.existe) return "áudio não encontrado";
  if (g.transcricao_estado === "transcrevendo") return "transcrevendo · " + Math.round((g.progresso || 0) * 100) + "%";
  if (g.transcricao_estado === "fila") return "na fila para transcrever";
  if (g.transcricao_estado === "pronta") return g.resumo ? "resumo pronto" : "transcrita";
  if (g.transcricao_estado === "erro") return "erro na transcrição";
  return "arquivada · sem transcrição";
}

function notaDaVoz() {
  const v = gv.voz;
  if (v && v.disponivel) return "Áudio, transcrição e resumo ficam nesta máquina · " + v.rotulo;
  return "Áudio fica nesta máquina · baixe o modelo de voz para transcrever aqui";
}

function rotuloDoModeloGv(nome) {
  const partes = String(nome || "").split(" ");
  const m = ((gv.voz || {}).modelos || []).find((x) => x.nome === partes[0]);
  return (m ? m.rotulo : (partes[0] || "Whisper")) + (partes.length > 1 ? " " + partes.slice(1).join(" ") : "");
}

/* Quanto costuma demorar: a medida desta maquina em CPU (turbo ~2,4x o tempo
   real, small ~6x), arredondada para cima porque promessa curta irrita. */
function estimativaGv(segundos) {
  const fator = (gv.voz || {}).modelo === "small" ? 5 : 2;
  const min = Math.max(1, Math.ceil(segundos / fator / 60));
  return min === 1 ? "cerca de 1 minuto" : "uns " + min + " minutos";
}

function realcarGv(texto, termo) {
  if (!termo) return esc(texto);
  const partes = texto.split(new RegExp("(" + termo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"));
  return partes.map((p, i) => (i % 2 ? "<mark>" + esc(p) + "</mark>" : esc(p))).join("");
}

function linhasDaTranscricao(g) {
  const termo = gv.buscaTrecho.trim();
  const trechos = termo ? g.trechos.filter((t) => t.texto.toLowerCase().includes(termo.toLowerCase())) : g.trechos;
  return trechos.map((t) => '<div class="gv-trecho"><button class="em-ligacao forte" data-gv-ir="' + Math.floor(t.inicio) + '">' + duracaoGv(t.inicio) + "</button><p>" +
    realcarGv(t.texto, termo) + "</p></div>").join("") || '<p class="nota">Nada com “' + esc(termo) + "” nesta transcrição.</p>";
}

function textoDoProgressoGv(g) {
  if (g.transcricao_estado === "fila") return "na fila" + (g.posicao_na_fila > 1 ? " · posição " + g.posicao_na_fila : " · outra gravação está sendo transcrita");
  return "transcrevendo nesta máquina · " + Math.round((g.progresso || 0) * 100) + "% · " + rotuloDoModeloGv((gv.voz || {}).modelo);
}

function textoDoDownloadGv(v) {
  const m = (v.modelos || []).find((x) => x.nome === v.baixando) || {};
  return "baixando " + (m.rotulo || "o modelo de voz") + " · " + (v.baixado_mb || 0) + " de " + (m.mb || "?") + " MB";
}

/* O que a aba Transcricao mostra depende do estado: sem modelo, baixar; sem
   transcricao, transcrever; na fila ou transcrevendo, o andamento; pronta,
   os trechos com o minuto clicavel e a busca com realce. */
function cartaoDaTranscricao(g) {
  const v = gv.voz || {};
  // A conta (palavras, modelo, tempo) mora no painel; aqui ficam as ferramentas.
  const cabeca = (meta, direita) => (direita ? '<div class="gv-ferramentas">' + direita + "</div>" : "");
  const corpo = (titulo, icone, texto, extra) => '<div class="gv-adiante"><b>' + ic(icone, 18) + esc(titulo) + "</b><p>" + texto + "</p>" + (extra || "") + "</div>";
  if (g.transcricao_estado === "pronta" && g.trechos && g.trechos.length) {
    const meta = "literal · " + duracaoLongaGv(g.duracao_s) + " · " + plural(g.palavras || 0, "palavra") + " · " + rotuloDoModeloGv(g.transcricao_modelo) +
      (g.transcricao_tempo ? " em " + duracaoLongaGv(g.transcricao_tempo) : "");
    return '<div class="gv-miolo gv-transcrita">' + cabeca(meta,
      '<label class="busca-tela gv-busca-trecho">' + ic("search", 18) + '<input type="text" placeholder="Buscar na transcrição…" data-gv-busca-trecho="1" value="' + esc(gv.buscaTrecho) + '"></label>' +
      '<button data-gv-corrigir="1">Corrigir nomes</button>' +
      '<button data-gv-exportar="1">Exportar .docx</button>' +
      '<button data-gv-copiar-transcricao="1">Copiar</button>') +
      '<div class="gv-trechos">' + linhasDaTranscricao(g) + "</div></div>";
  }
  if (!g.existe) {
    return '<div class="gv-miolo">' + cabeca("sem áudio") + corpo("O áudio não está mais no disco", "error",
      "Ele ficava em " + esc(gv.pasta) + ". Sem o arquivo não há o que transcrever.") + "</div>";
  }
  if (g.transcricao_estado === "fila" || g.transcricao_estado === "transcrevendo") {
    return '<div class="gv-miolo">' + cabeca("em andamento") + corpo("Transcrevendo nesta máquina", "graphic_eq",
      "O áudio não sai daqui. Dá para sair desta tela e voltar; a lista mostra o andamento e a transcrição aparece sozinha quando terminar.",
      '<div class="gv-progresso"><i id="gv-progresso" style="width:' + Math.round((g.progresso || 0) * 100) + '%"></i></div>' +
      '<small class="nota" id="gv-progresso-texto">' + esc(textoDoProgressoGv(g)) + "</small>") + "</div>";
  }
  if (g.transcricao_estado === "erro") {
    return '<div class="gv-miolo">' + cabeca("não deu certo") + corpo("A transcrição falhou", "error",
      esc(g.transcricao_erro || "erro desconhecido"),
      '<div class="fin-botoes"><button class="primario com-icone" data-gv-transcrever="1">' + ic("refresh", 16) + "Tentar de novo</button></div>") + "</div>";
  }
  if (v.disponivel) {
    return '<div class="gv-miolo">' + cabeca("ainda não transcrita") + corpo("Transcrever nesta máquina", "graphic_eq",
      "O " + esc(v.rotulo) + " lê o áudio aqui mesmo — nada sai do computador — e devolve o texto literal com o minuto de cada trecho. Para " +
      duracaoLongaGv(g.duracao_s) + " de áudio costuma levar " + estimativaGv(g.duracao_s) + "; roda em segundo plano.",
      '<div class="fin-botoes"><button class="primario com-icone" data-gv-transcrever="1">' + ic("graphic_eq", 16) + "Transcrever nesta máquina</button></div>") + "</div>";
  }
  if (v.baixando) {
    return '<div class="gv-miolo">' + cabeca("baixando o modelo de voz") + corpo("Baixando o modelo de voz", "download",
      "Uma vez só, com internet. Depois disso a transcrição roda aqui, sem mandar o áudio para fora.",
      '<small class="nota" id="gv-baixando-texto">' + esc(textoDoDownloadGv(v)) + "</small>") + "</div>";
  }
  const modelos = (v.modelos || []).map((m) => '<button class="' + (m.nome === v.modelo ? "primario " : "") + 'com-icone" data-gv-baixar-voz="' + m.nome + '">' +
    ic("download", 16) + "Baixar " + esc(m.rotulo) + " (" + esc(String(Math.round(m.mb / 100) / 10).replace(".", ",")) + " GB)</button>").join("");
  const notas = (v.modelos || []).map((m) => "<li><b>" + esc(m.rotulo) + "</b> — " + esc(m.nota) + "</li>").join("");
  return '<div class="gv-miolo">' + cabeca("sem modelo de voz nesta máquina") + corpo("Baixe o modelo de voz para transcrever aqui", "graphic_eq",
    "A transcrição é feita nesta máquina, e para isso o modelo de voz precisa estar baixado nela. É um download só, com internet; depois o áudio nunca sai do computador." +
    (v.erro ? '<br><span class="gv-erro">' + esc(v.erro) + "</span>" : ""),
    '<ul class="sv-falta">' + notas + "</ul>" + '<div class="fin-botoes">' + modelos + "</div>") + "</div>";
}

function cartaoDoResumoGv(g) {
  const transcrita = g.transcricao_estado === "pronta" && g.trechos && g.trechos.length;
  if (g.resumo) {
    return '<div class="gv-miolo gv-transcrita"><div class="gv-ferramentas"><small>escrito ' + esc(quandoCurtoSv(g.resumo_em)) + " · pelo modelo local, sobre a transcrição</small>" +
      '<div class="direita"><button data-gv-copiar-resumo="1">Copiar</button><button class="com-icone" data-gv-resumo="1"' + (gv.resumindo ? " disabled" : "") + ">" + ic("refresh", 16) +
      (gv.resumindo ? "escrevendo…" : "Atualizar resumo") + "</button></div></div>" +
      '<p class="gv-resumo-texto">' + esc(g.resumo) + "</p>" + blocoDePendenciasGv(g) + "</div>";
  }
  const cabeca = "";
  if (gv.resumindo) {
    return '<div class="gv-miolo">' + cabeca + '<div class="gv-adiante"><b>' + ic("auto_awesome", 18) + "Escrevendo o resumo…</b>" +
      "<p>O modelo local lê a transcrição inteira e escreve resumo, decisões e pendências. Em CPU leva alguns minutos; a tela espera aqui.</p></div></div>";
  }
  if (transcrita) {
    return '<div class="gv-miolo">' + cabeca + '<div class="gv-adiante"><b>' + ic("auto_awesome", 18) + "Pedir o resumo ao modelo local</b>" +
      "<p>Ele lê a transcrição e escreve: do que se tratou, o que foi decidido e o que ficou pendente — só com o que está dito, sem inventar nome, valor ou data. " +
      "Em CPU leva alguns minutos" + (g.palavras > 3000 ? ", e uma gravação longa é resumida em partes" : "") + ".</p>" +
      '<div class="fin-botoes"><button class="primario com-icone" data-gv-resumo="1">' + ic("refresh", 16) + "Fazer um resumo</button></div></div></div>";
  }
  return '<div class="gv-miolo">' + cabeca + '<div class="gv-adiante"><b>' + ic("auto_awesome", 18) + "O resumo nasce da transcrição</b>" +
    "<p>Transcreva a gravação primeiro; depois o modelo local escreve o resumo com decisões e pendências. Até lá, as suas notas no painel e os marcadores são o registro.</p>" +
    '<div class="fin-botoes"><button data-gv-aba="transcricao">Ir para a transcrição</button></div></div></div>';
}

/* ------------------------------------------ o que sai da transcricao */
/*
   O que o desenho poe ao lado da transcricao e do resumo: corrigir um nome
   que o modelo de voz errou, levar a transcricao em .docx, mandar o resumo
   por e-mail (que passa por Aprovacoes como qualquer envio) e transformar
   as pendencias do resumo em tarefas ou num compromisso na Agenda.
*/

async function corrigirNomesGv(g) {
  if (!g) return;
  const r = await dialogo({
    titulo: "Corrigir nomes", contexto: "Gravações › " + g.titulo,
    texto: "O modelo de voz erra nome próprio. A troca vale para a transcrição inteira e para o resumo; palavra inteira, sem diferenciar maiúsculas.",
    campos: [
      { chave: "de", rotulo: "Como saiu na transcrição", placeholder: "Priscilla", icone: "search" },
      { chave: "para", rotulo: "Como é", placeholder: "Priscila", icone: "person", sugestoes: g.participantes_lista || [], obrigatorio: true },
    ],
    confirmar: "Corrigir",
  });
  if (!r || !r.ok) return;
  const resp = await fetch("/api/gravacoes/" + g.id + "/corrigir", { method: "POST", headers: GV_JSON, body: JSON.stringify({ de: r.valores.de, para: r.valores.para }) });
  if (!resp.ok) { avisoCert(await erroDe(resp), { tom: "erro" }); return; }
  const d = await resp.json();
  gv.aberta = d;
  if (d.trocados) avisoCert(plural(d.trocados, "trecho") + (d.trocados === 1 ? " corrigido" : " corrigidos"), { tom: "ok" });
  else avisoCert("não achei “" + r.valores.de + "” na transcrição", { tom: "erro" });
  redesenharConteudoGv();
}

function baixarTranscricaoGv(g) {
  if (!g) return;
  const a = document.createElement("a");
  a.href = "/api/gravacoes/" + g.id + "/transcricao.docx";
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/* O e-mail nasce pronto - destinatario (o e-mail do cliente, se a ficha
   tem), assunto, o resumo no corpo e a transcricao em .docx anexa - e vai
   para a tela de escrever, que manda pela fila de Aprovacoes conforme o
   limite que a pessoa escolheu. */
async function compartilharResumoGv(g) {
  if (!g) return;
  if (!g.trechos || !g.trechos.length) { avisoCert("transcreva a gravação primeiro — o e-mail leva o resumo e a transcrição"); return; }
  if (!g.resumo) {
    const ok = await confirmar({ titulo: "Compartilhar sem resumo?", contexto: "Gravações › " + g.titulo,
      texto: "Ainda não há resumo. O e-mail vai só com a transcrição em anexo; dá para pedir o resumo antes, na aba Resumo.", confirmar: "Compartilhar assim" });
    if (!ok) return;
  }
  const r = await fetch("/api/gravacoes/" + g.id + "/exportar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const anexo = await r.json();
  let para = "";
  if (g.cadastro_id) {
    try {
      const d = await (await fetch("/api/cadastros?tipo=&termo=&ordem=nome")).json();
      const f = (d.fichas || []).find((x) => x.id === g.cadastro_id);
      if (f && f.email) para = f.email;
    } catch (err) { /* sem e-mail na ficha: a pessoa escreve */ }
  }
  const corpo = "Segue o resumo de “" + g.titulo + "” (" + quandoDaGravacao(g) + ").\n\n" + (g.resumo || "").trim() + "\n\nA transcrição completa vai em anexo.";
  const rascunho = { para: para, cc: "", cco: "", assunto: "Resumo · " + g.titulo, corpo: corpo, anexos: [anexo], quando: new Date().toISOString() };
  // O rascunho fica guardado nesta maquina: se ainda nao ha conta de e-mail,
  // a tela pede a conta e o e-mail continua pronto quando ela existir.
  try { localStorage.setItem("paulus.email.rascunho", JSON.stringify(rascunho)); } catch (err) { /* sem memoria local */ }
  marcarDestino("caixa");
  await telaEscrever(rascunho);
  if (mail.visao === "contas") avisoCert("cadastre uma conta de e-mail primeiro — o e-mail com o resumo fica guardado como rascunho", { tom: "erro" });
  else avisoCert("e-mail pronto para revisar — enviar passa por Aprovações conforme o seu limite", { tom: "ok" });
}

/* As pendencias que o modelo escreveu no resumo ("Pendências:" e uma linha
   por item), para virarem tarefas. A data, quando vem como dd/mm, "hoje",
   "amanhã" ou um dia da semana, vira prazo. */
function pendenciasDoResumo(texto) {
  const itens = [];
  let dentro = false;
  for (const bruta of String(texto || "").split("\n")) {
    const linha = bruta.trim();
    if (!linha) continue;
    if (/^pend[êe]ncias?\b/i.test(linha)) {
      dentro = true;
      const resto = linha.replace(/^pend[êe]ncias?\s*:?\s*/i, "").replace(/^[-•*\d.)\s]+/, "");
      if (resto && !/^nenhuma/i.test(resto)) itens.push(resto);
      continue;
    }
    if (/^(resumo|decis[õo]es|pr[óo]ximos passos|observa[çc][õo]es)\b/i.test(linha)) { if (dentro) break; continue; }
    if (!dentro) continue;
    const item = linha.replace(/^[-•*\d.)\s]+/, "").trim();
    if (item && !/^nenhuma/i.test(item)) itens.push(item);
  }
  return itens.map((t) => ({ texto: t, prazo: prazoNoTexto(t) }));
}

function prazoNoTexto(t) {
  const hoje = new Date();
  const m = /(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/.exec(t);
  if (m) {
    let ano = m[3] ? Number(m[3]) : hoje.getFullYear();
    if (ano < 100) ano += 2000;
    const d = new Date(ano, Number(m[2]) - 1, Number(m[1]));
    if (!isNaN(d) && d.getMonth() === Number(m[2]) - 1) return iso(d);
  }
  if (/\bhoje\b/i.test(t)) return iso(hoje);
  if (/\bamanh[ãa]\b/i.test(t)) { const d = new Date(hoje); d.setDate(d.getDate() + 1); return iso(d); }
  const dias = ["domingo", "segunda", "ter[çc]a", "quarta", "quinta", "sexta", "s[áa]bado"];
  for (let i = 0; i < 7; i++) {
    if (new RegExp("\\b" + dias[i] + "(-feira)?\\b", "i").test(t)) {
      const d = new Date(hoje);
      let delta = (i - d.getDay() + 7) % 7;
      if (delta === 0) delta = 7;
      d.setDate(d.getDate() + delta);
      return iso(d);
    }
  }
  return "";
}

function blocoDePendenciasGv(g) {
  const itens = pendenciasDoResumo(g.resumo);
  if (!itens.length) return '<div class="gv-pendencias"><p class="nota">O resumo não separou pendências. Se houver, peça um resumo novo — ou anote no painel.</p></div>';
  return '<div class="gv-pendencias"><div class="painel-bloco-cabeca">Pendências<span class="contagem">' + itens.length + "</span></div>" +
    itens.map((p, i) => '<label class="gv-pendencia"><input type="checkbox" data-gv-pendencia="' + i + '" checked><span>' + esc(p.texto) +
      (p.prazo ? ' <small>· prazo ' + esc(dataCurta(p.prazo)) + "</small>" : "") + "</span></label>").join("") +
    '<div class="fin-botoes"><button class="primario com-icone" data-gv-criar-tarefas="1">' + ic("add_task", 16) + "Criar tarefas</button>" +
    '<button class="com-icone" data-gv-agenda="1">' + ic("event_upcoming", 16) + "Levar para a Agenda</button></div></div>";
}

async function criarTarefasDoResumo(g) {
  if (!g) return;
  const itens = pendenciasDoResumo(g.resumo);
  const marcadas = Array.from(document.querySelectorAll("[data-gv-pendencia]")).filter((c) => c.checked).map((c) => itens[Number(c.dataset.gvPendencia)]).filter(Boolean);
  if (!marcadas.length) { avisoCert("marque ao menos uma pendência"); return; }
  let criadas = 0;
  for (const p of marcadas) {
    const r = await fetch("/api/tarefas", { method: "POST", headers: GV_JSON, body: JSON.stringify({ id: null, dados: {
      titulo: p.texto.slice(0, 140), prazo: p.prazo || "", cadastro_id: g.cadastro_id || null,
      anotacao: "Da gravação “" + g.titulo + "” (" + quandoDaGravacao(g) + ").",
    } }) });
    if (r.ok) criadas += 1;
  }
  if (g.servico_id && criadas) {
    fetch("/api/servicos/" + g.servico_id + "/anotacoes", { method: "POST", headers: GV_JSON, body: JSON.stringify({ texto: plural(criadas, "tarefa") + " da gravação “" + g.titulo + "” na Agenda." }) });
  }
  avisoCert(plural(criadas, "tarefa") + (criadas === 1 ? " criada" : " criadas") + " na Agenda", { tom: "ok" });
}

function levarParaAgendaGv(g) {
  if (!g) return;
  const itens = pendenciasDoResumo(g.resumo);
  ag.visao = "semana";
  ag.painel = "form";
  ag.form = Object.assign(compromissoEmBranco("compromisso"), {
    cadastro_id: g.cadastro_id || null, titulo: "Retorno · " + g.titulo,
    anotacao: itens.length ? "Pendências da gravação:\n" + itens.map((p) => "- " + p.texto).join("\n") : "Retorno da gravação “" + g.titulo + "”.",
  });
  marcarDestino("calendario");
  mostrarAgenda("semana");
}

function vigiarVoz() {
  clearTimeout(gv.relogioVoz);
  const v = gv.voz || {};
  const g = gv.aberta;
  const andando = (x) => x && (x.transcricao_estado === "fila" || x.transcricao_estado === "transcrevendo");
  const esperando = (gv.visao === "gravacao" && andando(g)) || (gv.visao === "lista" && gv.lista.some(andando)) || Boolean(v.baixando);
  if (!esperando) return;
  gv.relogioVoz = setTimeout(async () => {
    if (!$("gv-tela")) return;
    try {
      const voz = await (await fetch("/api/voz")).json();
      const baixava = Boolean((gv.voz || {}).baixando);
      gv.voz = voz;
      if (gv.visao === "lista") {
        const d = await (await fetch("/api/gravacoes?termo=" + encodeURIComponent(gv.termo))).json();
        gv.lista = d.gravacoes || [];
        gv.totalSegundos = d.total_segundos || 0;
        desenharGravacoes();
        return;
      }
      if (gv.visao === "gravacao" && g) {
        const r = await fetch("/api/gravacoes/" + g.id);
        if (r.ok) {
          const novo = await r.json();
          const mudou = novo.transcricao_estado !== gv.aberta.transcricao_estado;
          gv.aberta = novo;
          if (mudou) { cabecalhoGravacoes(); redesenharConteudoGv(); redesenharPainelGv(); }
          else {
            const barra = $("gv-progresso");
            if (barra) barra.style.width = Math.round((novo.progresso || 0) * 100) + "%";
            const texto = $("gv-progresso-texto");
            if (texto) texto.textContent = textoDoProgressoGv(novo);
          }
        }
      }
      if (baixava && !voz.baixando) { avisoCert(voz.disponivel ? "modelo de voz baixado — já dá para transcrever" : (voz.erro || "o download parou")); redesenharConteudoGv(); }
      else if (voz.baixando) { const t = $("gv-baixando-texto"); if (t) t.textContent = textoDoDownloadGv(voz); }
    } catch (err) { /* sem servidor neste tique: tenta no proximo */ }
    vigiarVoz();
  }, 2500);
}

async function transcreverGravacao() {
  const g = gv.aberta;
  const r = await fetch("/api/gravacoes/" + g.id + "/transcrever", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  gv.aberta = await r.json();
  cabecalhoGravacoes();
  redesenharConteudoGv();
  vigiarVoz();
}

async function baixarModeloDeVoz(nome) {
  let r = await fetch("/api/voz/modelo", { method: "POST", headers: GV_JSON, body: JSON.stringify({ modelo: nome }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  r = await fetch("/api/voz/baixar", { method: "POST", headers: GV_JSON, body: JSON.stringify({ modelo: nome }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  gv.voz = await r.json();
  avisoCert("baixando o modelo de voz — pode continuar usando o PAULUS; a tela avisa quando terminar");
  redesenharConteudoGv();
  vigiarVoz();
}

async function pedirResumoDaGravacao() {
  if (gv.resumindo) return;
  gv.resumindo = true;
  redesenharConteudoGv();
  redesenharPainelGv();
  const r = await fetch("/api/gravacoes/" + gv.aberta.id + "/resumo", { method: "POST" });
  gv.resumindo = false;
  if (!r.ok) {
    avisoCert("sem resumo agora: " + (await erroDe(r)));
  } else {
    gv.aberta = await r.json();
    cabecalhoGravacoes();
  }
  if ($("gv-tela")) { redesenharConteudoGv(); redesenharPainelGv(); }
}

function painelDaGravacao() {
  const g = gv.aberta;
  const servicos = '<option value="">sem serviço</option>' + gv.servicos.map((x) => '<option value="' + x.id + '"' + (x.id === g.servico_id ? " selected" : "") + ">" + esc(x.nome) + "</option>").join("");
  const clientes = '<option value="">sem cliente</option>' + gv.clientes.map((c) => '<option value="' + c.id + '"' + (c.id === g.cadastro_id ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("");
  const transcrita = g.transcricao_estado === "pronta";
  // Resumo da IA: o botão é o de Serviços - "atualizar resumo".
  const botaoResumo = transcrita
    ? '<button type="button" class="sv-ligacao" data-gv-resumo="1"' + (gv.resumindo ? " disabled" : "") + ">" + ic("refresh", 15) +
      (gv.resumindo ? "escrevendo…" : (g.resumo ? "atualizar resumo" : "fazer um resumo")) + "</button>"
    : "";
  const resumo = '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span class="gv-titulo-ic"><span class="sv-faisca">' + ic("auto_awesome", 16) + '</span>Resumo da IA</span><span class="contagem">' +
    esc(g.resumo ? "escrito " + quandoCurtoSv(g.resumo_em) : (transcrita ? "a fazer" : "depende da transcrição")) + "</span></div>" +
    (g.resumo
      ? '<p class="gv-resumo-curto">' + esc(g.resumo) + '</p><button class="em-ligacao forte" data-gv-aba="resumo">Ver o resumo inteiro</button>'
      : '<p class="nota">' + (transcrita ? "A transcrição está pronta. O modelo local pode escrever o resumo com decisões e pendências." : "O resumo nasce da transcrição: transcreva a gravação primeiro.") + "</p>") +
    botaoResumo + "</div>";
  // Anotações: as de Serviços - clicar edita, o x remove, Enter guarda.
  const anotacoes = (g.anotacoes || []).map((a, i) => '<div class="sv-anotacao"><div class="sv-anotacao-texto">' +
    '<p class="sv-editavel" data-gv-nota-editar="' + i + '" title="Clique para editar">' + esc(a.texto) + "</p>" +
    "<small>" + esc([a.quem, a.quando ? quandoCurtoSv(a.quando) : "", a.editada ? "editada" : ""].filter(Boolean).join(" · ")) + "</small></div>" +
    '<button type="button" class="mais-linha" data-gv-nota-tirar="' + i + '" title="Remover a anotação">' + ic("close", 15) + "</button></div>").join("");
  const blocoAnotacoes = '<div class="painel-bloco gv-anotacoes"><div class="painel-bloco-cabeca">Anotações<span class="contagem">' + ((g.anotacoes || []).length || "") + "</span></div>" +
    anotacoes + '<textarea class="sv-nova-nota" rows="1" placeholder="Nova anotação…  (Enter guarda)" data-gv-nota-nova="1"></textarea></div>';
  const onde = g.servico_nome ? "Pasta do serviço" : "Nesta máquina";
  const arquivado = '<div class="painel-bloco"><div class="painel-bloco-cabeca">Arquivado em</div>' +
    '<div class="gv-arquivado">' + ic(g.servico_nome ? "folder" : "inventory_2", 18) + '<div class="duas-linhas"><b>' + esc(onde) + "</b><small>" +
    esc([g.servico_nome ? "Serviços › " + g.servico_nome : "", g.mb + " MB", g.origem === "importada" ? "importada" : "gravada aqui"].filter(Boolean).join(" · ")) + "</small></div>" +
    (g.existe ? '<button class="mais-linha" data-gv-baixar="1" title="Baixar o áudio">' + ic("download", 16) + "</button>" : "") + "</div>" +
    '<div class="gv-arquivado">' + ic("work", 18) + '<div class="gv-ligar"><label>Serviço</label><select data-gv-ligar="servico_id">' + servicos + "</select>" +
    (g.servico_id ? '<button class="em-ligacao" data-gv-abrir-servico="' + g.servico_id + '">abrir a pasta do serviço</button>' : "<small>ligar move o áudio para a pasta do serviço</small>") + "</div></div>" +
    '<div class="gv-arquivado">' + ic("person", 18) + '<div class="gv-ligar"><label>Cliente</label><select data-gv-ligar="cadastro_id">' + clientes + "</select></div></div></div>";
  const detalheDaTranscricao = transcrita
    ? [plural(g.palavras || 0, "palavra"), plural(g.trechos_quantos || (g.trechos || []).length, "trecho"), rotuloDoModeloGv(g.transcricao_modelo),
      g.transcricao_tempo ? "levou " + duracaoLongaGv(g.transcricao_tempo) : ""].filter(Boolean).join(" · ")
    : (g.transcricao_estado === "fila" || g.transcricao_estado === "transcrevendo" ? "em andamento — a aba Transcrição mostra o progresso"
      : "ainda sem transcrição — Transcrever fica na aba Transcrição do Conteúdo");
  const transcricao = '<div class="painel-bloco"><div class="painel-bloco-cabeca">Transcrição<span class="contagem">' + esc(g.transcricao_rotulo || statusDaGravacao(g)) + "</span></div>" +
    '<p class="nota">' + esc(detalheDaTranscricao) + "</p></div>";
  return '<aside class="acervo-painel gv-painel"><div class="rolagem">' + resumo + blocoAnotacoes + arquivado + transcricao + "</div></aside>";
}

function posicaoDoAudio() {
  const a = $("gv-audio");
  return a ? a.currentTime || 0 : 0;
}

/* ------------------------------------------------------------ ligar */

function ligarGravacoes() {
  const clique = (sel, fn) => document.querySelectorAll(sel).forEach((b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });
  const busca = $("gv-busca");
  if (busca) {
    let t;
    busca.oninput = () => { clearTimeout(t); const v = busca.value; t = setTimeout(() => { gv.termo = v.trim(); mostrarGravacoes("lista"); }, 280); };
  }
  clique("[data-gv-voltar]", () => mostrarGravacoes("lista"));
  clique("[data-gv-nova]", () => { gv.aba = "vivo"; mostrarGravacoes("vivo"); });
  clique("[data-gv-vivo]", () => { gv.aba = "vivo"; mostrarGravacoes("vivo"); });
  clique("[data-gv-tipo]", (b) => { gv.tipo = b.dataset.gvTipo; desenharGravacoes(); });
  document.querySelectorAll("[data-gv-expandir]").forEach((linha) => {
    const id = Number(linha.dataset.gvExpandir);
    linha.onclick = (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey || gv.escolhidas.size) return;
      gv.expandida = gv.expandida === id ? null : id;
      desenharGravacoes();
    };
    linha.ondblclick = () => abrirGravacao(id);
  });
  ligarTocadorNaLinhaGv();
  ligarSelecao(document.querySelector("#gv-tela .gv-lista .tabela-corpo"), {
    linhas: ".tabela-linha[data-sel]", escolhidos: gv.escolhidas, aoMudar: desenharGravacoes,
    apagar: (ids) => apagarGravacoesEmLote(ids), renomear: (id) => renomearGravacao(Number(id)),
  });
  clique("[data-gv-sel-limpar]", () => { gv.escolhidas.clear(); desenharGravacoes(); });
  clique("[data-gv-sel-apagar]", () => apagarGravacoesEmLote([...gv.escolhidas]));
  clique("[data-gv-mais]", (b) => menuDaGravacao(b, gv.lista.find((x) => x.id === Number(b.dataset.gvMais))));
  clique("[data-gv-importar]", () => $("gv-importar").click());
  const importar = $("gv-importar");
  if (importar) importar.onchange = () => { if (importar.files[0]) importarAudioGv(importar.files[0]); };
  clique("[data-gv-adiante]", (b) => avisoCert(b.dataset.gvAdiante));
  clique("[data-gv-aba]", (b) => {
    const aba = b.dataset.gvAba;
    if (gv.visao === "vivo") {
      if (aba !== "vivo") {
        avisoCert(aba === "resumo" ? "O resumo é escrito depois, na gravação arquivada — a gravação continua"
          : ((gv.voz || {}).disponivel ? "A transcrição ao vivo está no cartão abaixo do gravador" : "A transcrição precisa do modelo de voz baixado nesta máquina"));
        return;
      }
      return;
    }
    gv.aba = aba;
    const alvo = $("gv-conteudo");
    if (alvo) { alvo.innerHTML = conteudoDaGravacao(); ligarGravacoes(); }
  });
  // ao vivo
  document.querySelectorAll("[data-gv-form]").forEach((el) => {
    el.oninput = () => { gv.vivo.form[el.dataset.gvForm] = /_id$/.test(el.dataset.gvForm) ? (Number(el.value) || null) : el.value; };
    el.onchange = el.oninput;
  });
  ligarParticipantesGv();
  clique("[data-gv-form-tipo]", (b) => { gv.vivo.form.tipo = b.dataset.gvFormTipo; document.querySelectorAll("[data-gv-form-tipo]").forEach((x) => x.classList.toggle("on", x === b)); });
  clique("[data-gv-comecar]", () => comecarGravacao());
  clique("[data-gv-pausar]", () => pausarGravacao());
  clique("[data-gv-parar]", () => pararGravacao());
  clique("[data-gv-marcar-vivo]", () => marcarMomentoAoVivo());
  clique("[data-gv-rolar]", (b) => { gv.vivo.rolar = !gv.vivo.rolar; b.classList.toggle("primario", gv.vivo.rolar); if (gv.vivo.rolar) desenharTrechosAoVivo(); });
  document.querySelectorAll("[data-gv-marcador-vivo]").forEach((el) => { el.oninput = () => { gv.vivo.marcadores[Number(el.dataset.gvMarcadorVivo)].texto = el.value; }; });
  clique("[data-gv-marcador-vivo-tirar]", (b) => { gv.vivo.marcadores.splice(Number(b.dataset.gvMarcadorVivoTirar), 1); redesenharPainelGv(); });
  // gravacao arquivada
  ligarTocador();
  clique("[data-gv-ir]", (b) => irParaGv(Number(b.dataset.gvIr)));
  clique("[data-gv-marcar]", () => marcarNaGravacao());
  const marcarTexto = document.querySelector("[data-gv-marcar-texto]");
  if (marcarTexto) {
    marcarTexto.oninput = () => { gv.marcarTexto = marcarTexto.value; };
    marcarTexto.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); marcarNaGravacao(); } };
  }
  document.querySelectorAll("[data-gv-marcador]").forEach((el) => {
    el.onchange = () => renomearMarcadorGv(Number(el.dataset.gvMarcador), el.value);
  });
  clique("[data-gv-marcador-tirar]", (b) => tirarMarcadorGv(Number(b.dataset.gvMarcadorTirar)));
  const novaNota = document.querySelector("[data-gv-nota-nova]");
  if (novaNota) novaNota.onkeydown = (e) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    e.preventDefault();
    if (novaNota.value.trim()) anotarNaGravacao("/api/gravacoes/" + gv.aberta.id + "/anotacoes", "POST", { texto: novaNota.value.trim() });
  };
  clique("[data-gv-nota-editar]", (b) => {
    const i = Number(b.dataset.gvNotaEditar);
    editarNoLugar(b, { valor: gv.aberta.anotacoes[i].texto, varias: true,
      aoGuardar: (novo) => anotarNaGravacao("/api/gravacoes/" + gv.aberta.id + "/anotacoes/" + i, "POST", { texto: novo }) });
  });
  clique("[data-gv-nota-tirar]", async (b) => {
    const i = Number(b.dataset.gvNotaTirar);
    const a = gv.aberta.anotacoes[i];
    if (!(await confirmar({ titulo: "Remover esta anotação?", contexto: "Gravações › " + gv.aberta.titulo,
      texto: "“" + a.texto.slice(0, 140) + (a.texto.length > 140 ? "…" : "") + "”", confirmar: "Remover", perigo: true }))) return;
    anotarNaGravacao("/api/gravacoes/" + gv.aberta.id + "/anotacoes/" + i, "DELETE");
  });
  clique("[data-gv-baixar]", () => baixarAudioGv(gv.aberta));
  document.querySelectorAll("[data-gv-ligar]").forEach((el) => { el.onchange = () => ligarGravacaoA(el.dataset.gvLigar, Number(el.value) || null); });
  clique("[data-gv-abrir-servico]", (b) => abrirServico(Number(b.dataset.gvAbrirServico)));
  clique("[data-gv-perguntar]", () => perguntarSobreGravacao(gv.aberta));
  // transcricao e resumo
  clique("[data-gv-transcrever]", () => transcreverGravacao());
  clique("[data-gv-baixar-voz]", (b) => baixarModeloDeVoz(b.dataset.gvBaixarVoz));
  clique("[data-gv-resumo]", () => pedirResumoDaGravacao());
  clique("[data-gv-copiar-transcricao]", () => copiarTexto(gv.aberta.trechos.map((t) => "[" + duracaoGv(t.inicio) + "] " + t.texto).join("\n"), "transcrição copiada"));
  clique("[data-gv-copiar-resumo]", () => copiarTexto(gv.aberta.resumo || "", "resumo copiado"));
  clique("[data-gv-corrigir]", () => corrigirNomesGv(gv.aberta));
  clique("[data-gv-exportar]", () => baixarTranscricaoGv(gv.aberta));
  clique("[data-gv-compartilhar]", () => compartilharResumoGv(gv.aberta));
  clique("[data-gv-criar-tarefas]", () => criarTarefasDoResumo(gv.aberta));
  clique("[data-gv-agenda]", () => levarParaAgendaGv(gv.aberta));
  const buscaTrecho = document.querySelector("[data-gv-busca-trecho]");
  if (buscaTrecho) buscaTrecho.oninput = () => {
    gv.buscaTrecho = buscaTrecho.value;
    const alvo = document.querySelector("#gv-conteudo .gv-trechos");
    if (alvo) { alvo.innerHTML = linhasDaTranscricao(gv.aberta); ligarGravacoes(); }
  };
}

function redesenharPainelGv() {
  const velho = document.querySelector("#gv-tela .acervo-painel");
  if (!velho) return;
  velho.outerHTML = gv.visao === "vivo" ? painelAoVivo() : painelDaGravacao();
  ligarGravacoes();
}

/* --------------------------------------------------- gravar ao vivo */

async function comecarGravacao() {
  const v = gv.vivo;
  if (v.estado !== "pronto") return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
    v.erro = "Este navegador não dá acesso ao microfone aqui. Abra o PAULUS na janela do programa ou no Edge.";
    desenharGravacoes();
    return;
  }
  let fluxo;
  try {
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    v.erro = err && err.name === "NotAllowedError"
      ? "O microfone foi negado. Libere o microfone para o PAULUS nas permissões da janela e tente de novo."
      : (err && err.name === "NotFoundError" ? "Nenhum microfone encontrado nesta máquina." : "Não consegui abrir o microfone: " + (err && err.message ? err.message : err));
    desenharGravacoes();
    return;
  }
  const tipos = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  const mime = tipos.find((t) => MediaRecorder.isTypeSupported(t)) || "";
  const gravador = mime ? new MediaRecorder(fluxo, { mimeType: mime }) : new MediaRecorder(fluxo);
  v.pedacos = [];
  v.marcadores = [];
  v.erro = "";
  gravador.ondataavailable = (e) => { if (e.data && e.data.size) v.pedacos.push(e.data); };
  gravador.start(1000);
  v.gravador = gravador;
  v.fluxo = fluxo;
  v.estado = "gravando";
  v.inicio = Date.now();
  v.decorrido = 0;
  clearInterval(v.relogio);
  v.relogio = setInterval(tiquetaqueGv, 500);
  if (!v.form.titulo) v.form.titulo = tituloPadraoGv(v.form);
  comecarTranscricaoAoVivo(fluxo);
  desenharGravacoes();
  ligarEqualizadorVivo(fluxo);
}

function tiquetaqueGv() {
  const texto = duracaoGv(segundosGravados());
  const el = $("gv-tempo");
  if (el) el.textContent = texto;
  const linha = $("gv-tempo-linha");
  if (linha) linha.textContent = texto;
}

function pausarGravacao() {
  const v = gv.vivo;
  if (!v.gravador) return;
  if (v.estado === "gravando") {
    v.gravador.pause();
    v.decorrido += Date.now() - v.inicio;
    v.estado = "pausada";
  } else if (v.estado === "pausada") {
    v.gravador.resume();
    v.inicio = Date.now();
    v.estado = "gravando";
  }
  desenharGravacoes();
}

function marcarMomentoAoVivo() {
  const v = gv.vivo;
  if (v.estado === "pronto" || v.estado === "salvando") return;
  v.marcadores.push({ t: Math.round(segundosGravados()), texto: "" });
  redesenharPainelGv();
  const campos = document.querySelectorAll("[data-gv-marcador-vivo]");
  const ultimo = campos[campos.length - 1];
  if (ultimo) ultimo.focus();
  const rodape = $("gv-vivo-rodape");
  if (rodape) rodape.textContent = rodapeDoGravadorGv();
}

function limparGravacaoAoVivo() {
  const v = gv.vivo;
  clearInterval(v.relogio);
  clearInterval(v.relogioEnvio);
  pararCaptura(v);
  pararEqualizadorVivo();
  if (v.fluxo) v.fluxo.getTracks().forEach((t) => t.stop());
  Object.assign(v, { estado: "pronto", inicio: 0, decorrido: 0, relogio: null, gravador: null, pedacos: [], fluxo: null, marcadores: [], erro: "",
    form: { titulo: "", tipo: "reuniao", cadastro_id: null, servico_id: null, participantes: "" },
    sessao: "", captura: null, amostras: [], enviando: false, relogioEnvio: null, enviados: 0, transcricao: [], rolar: true, avisoVivo: "" });
}

async function pararGravacao() {
  const v = gv.vivo;
  if (!v.gravador || v.estado === "salvando") return;
  if (v.estado === "gravando") v.decorrido += Date.now() - v.inicio;
  v.estado = "salvando";
  desenharGravacoes();
  const gravador = v.gravador;
  const blob = await new Promise((resolve) => {
    gravador.onstop = () => resolve(new Blob(v.pedacos, { type: gravador.mimeType || "audio/webm" }));
    gravador.stop();
  });
  v.fluxo.getTracks().forEach((t) => t.stop());
  pararEqualizadorVivo();
  clearInterval(v.relogio);
  const mime = gravador.mimeType || "";
  const extensao = /ogg/.test(mime) ? ".ogg" : (/mp4/.test(mime) ? ".m4a" : ".webm");
  const sessao = await encerrarTranscricaoAoVivo();
  const dados = new FormData();
  dados.append("arquivo", blob, "gravacao" + extensao);
  dados.append("sessao", sessao || "");
  dados.append("titulo", v.form.titulo || tituloPadraoGv(v.form));
  dados.append("tipo", v.form.tipo);
  dados.append("cadastro_id", v.form.cadastro_id ? String(v.form.cadastro_id) : "");
  dados.append("servico_id", v.form.servico_id ? String(v.form.servico_id) : "");
  dados.append("participantes", v.form.participantes);
  dados.append("duracao_s", String(Math.round(v.decorrido / 1000)));
  dados.append("origem", "gravada");
  dados.append("marcadores", JSON.stringify(v.marcadores));
  const r = await fetch("/api/gravacoes", { method: "POST", body: dados });
  if (!r.ok) {
    avisoCert("não consegui guardar o áudio: " + (await erroDe(r)));
    v.estado = "pausada";
    v.gravador = null;
    desenharGravacoes();
    return;
  }
  const g = await r.json();
  limparGravacaoAoVivo();
  avisoCert("gravação arquivada nesta máquina · " + duracaoLongaGv(g.duracao_s));
  gv.aberta = g;
  gv.aba = "transcricao";
  mostrarGravacoes("gravacao");
}

/* ------------------------------------------------------- ao vivo */
/*
   A transcricao enquanto grava. Um AudioWorklet captura o microfone em
   PCM, a cada 2 s o que juntou vai ao servidor (16 kHz, 16 bits), e o
   servidor devolve trechos quando acha uma pausa na fala. O texto entra no
   cartao abaixo do gravador, com o minuto. Ao parar, o que sobrou e
   transcrito e a sessao vai junto com o audio: a gravacao ja nasce
   transcrita.
*/

const GV_CAPTADOR = 'class Captador extends AudioWorkletProcessor { process(entradas) { const canal = entradas[0] && entradas[0][0]; if (canal) this.port.postMessage(canal.slice(0)); return true; } } registerProcessor("paulus-captador", Captador);';

function linhaAoVivo(t) {
  return '<div class="gv-trecho"><span class="em-ligacao forte fixo">' + duracaoGv(t.inicio) + "</span><p>" + esc(t.texto) + "</p></div>";
}

function rodapeAoVivo() {
  const v = gv.vivo;
  if (v.avisoVivo) return '<p class="nota gv-vivo-aviso">' + esc(v.avisoVivo) + "</p>";
  const classe = "gv-ouvindo" + (v.estado === "gravando" && v.sessao ? " viva" : "");
  let texto;
  if (v.estado === "pausada") texto = "pausada — volta a ouvir quando a gravação continuar";
  else if (v.estado === "salvando") texto = "transcrevendo o que sobrou…";
  else if (!v.sessao) texto = "abrindo a sessão de transcrição…";
  else texto = v.transcricao.length ? "ouvindo… o próximo trecho chega na próxima pausa" : "ouvindo… o texto chega a cada pausa na fala, alguns segundos depois";
  return '<div class="' + classe + '"><i class="gv-pulso"></i>' + texto + "</div>";
}

function cartaoAoVivo() {
  const v = gv.vivo;
  const voz = gv.voz || {};
  const cabeca = (meta, direita) => '<div class="fin-cartao-cabeca"><span>Transcrição ao vivo</span><small>' + esc(meta) + "</small>" +
    (direita ? '<div class="direita">' + direita + "</div>" : "") + "</div>";
  if (!voz.disponivel) {
    return '<div class="fin-cartao gv-transcricao">' + cabeca("sem modelo de voz nesta máquina") +
      '<div class="gv-adiante"><b>' + ic("graphic_eq", 18) + "Ainda sem modelo de voz nesta máquina</b>" +
      "<p>A transcrição ao vivo — literal, com o minuto de cada trecho — precisa do modelo de voz baixado aqui, para o áudio não sair do computador. " +
      "O áudio é gravado normalmente e os marcadores guardam os momentos que importam; baixe o modelo pela aba Transcrição de qualquer gravação ou em Configurações.</p></div></div>";
  }
  if (v.estado === "pronto") {
    return '<div class="fin-cartao gv-transcricao">' + cabeca("literal · " + voz.rotulo + " · alguns segundos depois da fala") +
      '<div class="gv-adiante"><b>' + ic("graphic_eq", 18) + "Começa junto com a gravação</b>" +
      "<p>O áudio vai em pedaços para o modelo nesta máquina, que devolve o texto a cada pausa na fala — com o minuto, alguns segundos depois. Nada sai do computador. " +
      "Ao parar e arquivar, a gravação já nasce transcrita. Separar quem disse o quê ainda não existe.</p></div></div>";
  }
  return '<div class="fin-cartao gv-transcricao">' + cabeca("literal · " + voz.rotulo + " · " + plural(v.transcricao.length, "trecho"),
    '<button data-gv-adiante="Corrigir nomes fica para depois de arquivar: na gravação, a troca vale para a transcrição inteira">Corrigir nomes</button>' +
    '<button class="' + (v.rolar ? "primario" : "") + '" data-gv-rolar="1">Rolar junto</button>') +
    '<div class="gv-vivo-trechos" id="gv-vivo-trechos">' + v.transcricao.map(linhaAoVivo).join("") + rodapeAoVivo() + "</div></div>";
}

function desenharTrechosAoVivo() {
  const alvo = $("gv-vivo-trechos");
  if (!alvo) return;
  const v = gv.vivo;
  alvo.innerHTML = v.transcricao.map(linhaAoVivo).join("") + rodapeAoVivo();
  const meta = document.querySelector("#gv-tela .gv-transcricao .fin-cartao-cabeca small");
  if (meta) meta.textContent = "literal · " + ((gv.voz || {}).rotulo || "") + " · " + plural(v.transcricao.length, "trecho");
  if (v.rolar) alvo.scrollTop = alvo.scrollHeight;
}

async function comecarTranscricaoAoVivo(fluxo) {
  const v = gv.vivo;
  v.transcricao = [];
  v.avisoVivo = "";
  v.sessao = "";
  v.amostras = [];
  v.enviados = 0;
  if (!gv.voz || !gv.voz.disponivel) return;
  let r = null;
  try { r = await fetch("/api/voz/ao-vivo", { method: "POST", headers: GV_JSON, body: "{}" }); } catch (err) { r = null; }
  if (!r || !r.ok) {
    v.avisoVivo = "não consegui abrir a transcrição ao vivo" + (r ? ": " + (await erroDe(r)) : " — o servidor não respondeu");
    desenharTrechosAoVivo();
    return;
  }
  const sessao = (await r.json()).sessao;
  if (v.estado === "pronto") { fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }); return; }
  v.sessao = sessao;
  try {
    let ctx;
    try { ctx = new AudioContext({ sampleRate: 16000 }); } catch (err) { ctx = new AudioContext(); }
    const fonte = ctx.createMediaStreamSource(fluxo);
    await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([GV_CAPTADOR], { type: "application/javascript" })));
    const no = new AudioWorkletNode(ctx, "paulus-captador");
    no.port.onmessage = (e) => { if (v.estado === "gravando" && v.sessao) v.amostras.push(e.data); };
    fonte.connect(no);
    no.connect(ctx.destination);
    v.captura = { ctx: ctx, no: no, fonte: fonte };
  } catch (err) {
    v.avisoVivo = "esta janela não deixou capturar o áudio para transcrever (" + (err && err.message ? err.message : err) + "); a gravação continua e a transcrição sai ao arquivar";
    desenharTrechosAoVivo();
    return;
  }
  clearInterval(v.relogioEnvio);
  v.relogioEnvio = setInterval(enviarPedacoAoVivo, 2000);
  desenharTrechosAoVivo();
}

function pcm16De(f32) {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const x = Math.max(-1, Math.min(1, f32[i]));
    out[i] = x < 0 ? x * 32768 : x * 32767;
  }
  return out.buffer;
}

/* Quando a janela nao aceita um contexto a 16 kHz, o audio vem na taxa do
   aparelho e e reamostrado aqui, por interpolacao linear: para voz basta. */
function reamostrarGv(f32, de, para) {
  if (de === para) return f32;
  const razao = de / para;
  const n = Math.floor(f32.length / razao);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const p = i * razao;
    const j = Math.floor(p);
    const f = p - j;
    out[i] = f32[j] * (1 - f) + (f32[Math.min(j + 1, f32.length - 1)] || 0) * f;
  }
  return out;
}

async function enviarPedacoAoVivo() {
  const v = gv.vivo;
  if (!v.sessao || v.enviando || !v.amostras.length) return;
  const partes = v.amostras;
  v.amostras = [];
  const total = partes.reduce((s, p) => s + p.length, 0);
  const junto = new Float32Array(total);
  let i = 0;
  partes.forEach((p) => { junto.set(p, i); i += p.length; });
  const taxa = v.captura ? v.captura.ctx.sampleRate : 16000;
  const pcm = pcm16De(reamostrarGv(junto, taxa, 16000));
  v.enviando = true;
  try {
    const r = await fetch("/api/voz/ao-vivo/" + v.sessao + "/audio", { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm });
    if (!r.ok) {
      v.avisoVivo = "a transcrição ao vivo parou: " + (await erroDe(r)) + " — a gravação continua e a transcrição sai ao arquivar";
      clearInterval(v.relogioEnvio);
      desenharTrechosAoVivo();
      return;
    }
    const d = await r.json();
    v.enviados += 1;
    if (d.trechos && d.trechos.length) {
      v.transcricao = v.transcricao.concat(d.trechos);
      desenharTrechosAoVivo();
    }
  } catch (err) {
    v.amostras = partes.concat(v.amostras);
  } finally {
    v.enviando = false;
  }
}

function pararCaptura(v) {
  if (!v.captura) return;
  try { v.captura.no.disconnect(); v.captura.fonte.disconnect(); v.captura.ctx.close(); } catch (err) { /* ja fechado */ }
  v.captura = null;
}

/* A gravacao parou: manda o que sobrou, fecha a sessao e devolve o id para
   ir junto com o audio. */
async function encerrarTranscricaoAoVivo() {
  const v = gv.vivo;
  clearInterval(v.relogioEnvio);
  pararCaptura(v);
  if (!v.sessao) return "";
  while (v.enviando) await new Promise((fim) => setTimeout(fim, 100));
  if (v.amostras.length) await enviarPedacoAoVivo();
  try {
    const r = await fetch("/api/voz/ao-vivo/" + v.sessao + "/fim", { method: "POST" });
    if (r.ok) {
      const d = await r.json();
      if (d.trechos) v.transcricao = d.trechos;
      desenharTrechosAoVivo();
    }
  } catch (err) { /* o servidor ainda guarda a sessao; ela vai junto com o audio */ }
  return v.sessao;
}

/* ------------------------------------------------------- importar */

function duracaoDoArquivoGv(arquivo) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(arquivo);
    const audio = new Audio();
    const fim = (s) => { URL.revokeObjectURL(url); resolve(isFinite(s) ? Math.round(s) : 0); };
    audio.onloadedmetadata = () => fim(audio.duration);
    audio.onerror = () => fim(0);
    setTimeout(() => fim(0), 8000);
    audio.src = url;
  });
}

async function importarAudioGv(arquivo) {
  avisoCert("lendo " + arquivo.name + "…");
  const segundos = await duracaoDoArquivoGv(arquivo);
  const dados = new FormData();
  dados.append("arquivo", arquivo, arquivo.name);
  dados.append("titulo", arquivo.name.replace(/\.[^.]+$/, ""));
  dados.append("tipo", gv.tipo || "reuniao");
  dados.append("duracao_s", String(segundos));
  dados.append("origem", "importada");
  const r = await fetch("/api/gravacoes", { method: "POST", body: dados });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const g = await r.json();
  avisoCert(g.titulo + " importada" + (segundos ? " · " + duracaoLongaGv(segundos) : ""));
  gv.aberta = g;
  mostrarGravacoes("gravacao");
}

/* ---------------------------------------------------------- tocador */

function ligarTocador() {
  const audio = $("gv-audio");
  if (!audio) return;
  const g = gv.aberta;
  const total = () => (isFinite(audio.duration) && audio.duration ? audio.duration : g.duracao_s);
  const botao = document.querySelector("[data-gv-tocar]");
  audio.playbackRate = gv.velocidade;
  const pintar = () => {
    const pos = $("gv-posicao");
    if (pos) pos.textContent = duracaoGv(audio.currentTime);
    const fill = $("gv-barra-fill");
    if (fill) fill.style.width = porcentagemGv(audio.currentTime, total()) + "%";
    const em = $("gv-marcar-em");
    if (em) em.textContent = duracaoGv(audio.currentTime);
  };
  audio.ontimeupdate = pintar;
  const estado = (tocando) => {
    if (botao) botao.innerHTML = ic(tocando ? "pause" : "play_arrow", 16) + (tocando ? "Pausar" : "Tocar");
    const nome = $("gv-player-nome");
    if (nome) nome.textContent = tocando ? "Tocando" : (audio.currentTime > 0 && !audio.ended ? "Em pausa" : "Pronto para ouvir");
    const cartao = $("gv-player");
    if (cartao) cartao.classList.toggle("tocando", tocando);
    if (tocando) { equalizadorDoTocadorGv(audio); if (!gv.quadroTocador) animarTocadorGv(); } else animarTocadorGv();
  };
  audio.onplay = () => estado(true);
  audio.onpause = () => estado(false);
  audio.onended = () => estado(false);
  animarTocadorGv();
  audio.onerror = () => avisoCert("não consegui tocar o áudio — o formato pode não ser reconhecido por esta janela");
  if (botao) botao.onclick = () => { if (audio.paused) audio.play(); else audio.pause(); };
  document.querySelectorAll("[data-gv-pular]").forEach((b) => {
    b.onclick = () => { audio.currentTime = Math.max(0, Math.min(total(), audio.currentTime + Number(b.dataset.gvPular))); pintar(); };
  });
  const vel = document.querySelector("[data-gv-velocidade]");
  if (vel) vel.onclick = () => {
    const i = GV_VELOCIDADES.indexOf(gv.velocidade);
    gv.velocidade = GV_VELOCIDADES[(i + 1) % GV_VELOCIDADES.length];
    audio.playbackRate = gv.velocidade;
    vel.textContent = velocidadeGv();
  };
  const barra = document.querySelector("[data-gv-barra]");
  if (barra) barra.onclick = (e) => {
    const caixa = barra.getBoundingClientRect();
    const fracao = Math.max(0, Math.min(1, (e.clientX - caixa.left) / caixa.width));
    audio.currentTime = fracao * total();
    pintar();
  };
}

/* O equalizador da gravação aberta: o mesmo desenho do ditado (barras finas
   espelhadas a partir do centro), lendo o som que está tocando. O contexto
   de áudio nasce no primeiro Tocar - a janela só deixa depois de um clique -
   e cada elemento de áudio só pode ser ligado a um contexto uma vez. */
function equalizadorDoTocadorGv(audio) {
  if (audio.analisadorGv) {
    if (gv.contextoTocador && gv.contextoTocador.state === "suspended") gv.contextoTocador.resume().catch(() => {});
    return audio.analisadorGv;
  }
  const Contexto = window.AudioContext || window.webkitAudioContext;
  if (!Contexto) return null;
  try {
    if (gv.contextoTocador) gv.contextoTocador.close().catch(() => {});
    const contexto = new Contexto();
    const analisador = contexto.createAnalyser();
    analisador.fftSize = 256;
    analisador.smoothingTimeConstant = 0.72;
    contexto.createMediaElementSource(audio).connect(analisador);
    analisador.connect(contexto.destination);
    gv.contextoTocador = contexto;
    audio.analisadorGv = analisador;
    return analisador;
  } catch (err) {
    return null;
  }
}

function animarTocadorGv() {
  const audio = $("gv-audio");
  const tela = document.querySelector("[data-gv-onda-tocador]");
  if (!audio || !tela) { gv.quadroTocador = 0; return; }
  const tocando = !audio.paused && !audio.ended;
  let dados = null;
  if (tocando && audio.analisadorGv) {
    dados = new Uint8Array(audio.analisadorGv.frequencyBinCount);
    audio.analisadorGv.getByteFrequencyData(dados);
  }
  desenharOnda(tela, dados, tocando);
  gv.quadroTocador = tocando ? requestAnimationFrame(animarTocadorGv) : 0;
}

function irParaGv(segundo) {
  const audio = $("gv-audio");
  if (!audio) { avisoCert("o áudio desta gravação não está mais no disco"); return; }
  audio.currentTime = segundo;
  audio.play();
}

async function marcarNaGravacao() {
  const g = gv.aberta;
  const r = await fetch("/api/gravacoes/" + g.id + "/marcadores", { method: "POST", headers: GV_JSON, body: JSON.stringify({ t: Math.round(posicaoDoAudio()), texto: gv.marcarTexto }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  g.marcadores = (await r.json()).marcadores;
  gv.marcarTexto = "";
  redesenharConteudoGv();
}

async function renomearMarcadorGv(i, texto) {
  const g = gv.aberta;
  const m = g.marcadores[i];
  if (!m || m.texto === texto) return;
  // O servidor so tem "por" e "tirar": renomear e tirar e por de novo no mesmo minuto.
  let r = await fetch("/api/gravacoes/" + g.id + "/marcadores/" + i, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  r = await fetch("/api/gravacoes/" + g.id + "/marcadores", { method: "POST", headers: GV_JSON, body: JSON.stringify({ t: m.t, texto: texto }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  g.marcadores = (await r.json()).marcadores;
}

async function tirarMarcadorGv(i) {
  const g = gv.aberta;
  const r = await fetch("/api/gravacoes/" + g.id + "/marcadores/" + i, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  g.marcadores = (await r.json()).marcadores;
  redesenharConteudoGv();
}

function redesenharConteudoGv() {
  const alvo = $("gv-conteudo");
  if (alvo) alvo.innerHTML = conteudoDaGravacao();
  const barra = document.querySelector("[data-gv-barra]");
  if (barra) {
    barra.querySelectorAll("u").forEach((u) => u.remove());
    gv.aberta.marcadores.forEach((m) => {
      const u = document.createElement("u");
      u.style.left = porcentagemGv(m.t, gv.aberta.duracao_s) + "%";
      u.title = m.texto || duracaoGv(m.t);
      barra.appendChild(u);
    });
  }
  ligarGravacoes();
}

/* Ligar a gravação a um serviço sem abrir a gravação: pelo "⋯" da linha. */
async function ligarGravacaoDaLista(g, servicoId) {
  if ((g.servico_id || null) === servicoId) return;
  const r = await fetch("/api/gravacoes/" + g.id, { method: "POST", headers: GV_JSON, body: JSON.stringify({ servico_id: servicoId }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const nova = await r.json();
  const i = gv.lista.findIndex((x) => x.id === g.id);
  if (i >= 0) gv.lista[i] = Object.assign({}, gv.lista[i], nova);
  const servico = gv.servicos.find((x) => x.id === servicoId);
  avisoCert(servico ? "“" + g.titulo + "” ligada a " + servico.nome : "“" + g.titulo + "” sem serviço", { tom: "ok" });
  desenharGravacoes();
}

async function ligarGravacaoA(campo, valor) {
  const g = gv.aberta;
  const dados = {};
  dados[campo] = valor;
  const r = await fetch("/api/gravacoes/" + g.id, { method: "POST", headers: GV_JSON, body: JSON.stringify(dados) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  gv.aberta = await r.json();
  cabecalhoGravacoes();
  redesenharPainelGv();
}

function apagarGravacoesEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/gravacoes/" + id, {
    rotulo: "gravação", plural: "gravações", contexto: "Gravações", texto: "O áudio, a transcrição e as notas saem da lista.",
    depois: () => { gv.escolhidas.clear(); mostrarGravacoes("lista"); },
  });
}

async function renomearGravacaoAberta(novo) {
  const g = gv.aberta;
  if (!g) return false;
  const r = await fetch("/api/gravacoes/" + g.id, { method: "POST", headers: GV_JSON, body: JSON.stringify({ titulo: novo }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  const salvo = await r.json();
  g.titulo = salvo.titulo;
  return true;
}

async function anotarNaGravacao(url, metodo, corpo) {
  const r = await fetch(url, { method: metodo, headers: GV_JSON, body: corpo ? JSON.stringify(corpo) : undefined });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return false; }
  gv.aberta.anotacoes = (await r.json()).anotacoes || [];
  redesenharPainelGv();
  return true;
}

async function renomearGravacao(id) {
  const g = gv.lista.find((x) => x.id === id);
  if (!g) return;
  const novo = await perguntar({ titulo: "Renomear gravação", contexto: "Gravações", campo: { rotulo: "Título", valor: g.titulo, icone: "graphic_eq" }, confirmar: "Renomear" });
  if (!novo) return;
  const r = await fetch("/api/gravacoes/" + id, { method: "POST", headers: GV_JSON, body: JSON.stringify({ titulo: novo }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  mostrarGravacoes("lista");
}

function menuDaGravacao(botao, g) {
  if (!g) return;
  menuNaLinha(botao, [
    { rotulo: "Abrir", icone: "graphic_eq", acao: () => abrirGravacao(g.id) },
    { rotulo: "Renomear", icone: "edit", acao: () => renomearGravacao(g.id) },
    { rotulo: "Ligar a um serviço", sub: [{ rotulo: "Sem serviço", atual: !g.servico_id, acao: () => ligarGravacaoDaLista(g, null) }, "-"]
      .concat(gv.servicos.map((x) => ({ rotulo: x.nome, atual: x.id === g.servico_id, acao: () => ligarGravacaoDaLista(g, x.id) }))) },
    { rotulo: "Baixar o áudio", icone: "download", acao: () => baixarAudioGv(g) },
    "-",
    { rotulo: "Apagar", icone: "delete", perigo: true, acao: () => apagarGravacao(g) },
  ]);
}

/* Baixar o áudio. Na janela do programa o link com `download` não leva a
   lugar nenhum: abre o "Salvar como" do Windows e o servidor copia o arquivo
   para lá. No navegador, o próprio download. */
async function baixarAudioGv(g) {
  if (!g || !g.existe) { avisoCert("o áudio não está mais no disco"); return; }
  const api = (window.pywebview || {}).api;
  if (api && api.salvar_como) {
    const r = await fetch("/api/gravacoes/" + g.id + "/audio/nome");
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const nome = (await r.json()).nome;
    const extensao = nome.split(".").pop();
    const caminho = await api.salvar_como(nome, ["Áudio (*." + extensao + ")"]);
    if (!caminho) return;
    const salvo = await fetch("/api/gravacoes/" + g.id + "/audio/salvar", { method: "POST", headers: GV_JSON, body: JSON.stringify({ caminho: caminho }) });
    if (!salvo.ok) { avisoCert(await erroDe(salvo), { tom: "erro" }); return; }
    avisoCert("áudio salvo · " + (await salvo.json()).nome, { tom: "ok" });
    return;
  }
  location.href = "/api/gravacoes/" + g.id + "/audio?baixar=1";
}

async function apagarGravacao(g) {
  if (!(await confirmar({ titulo: "Apagar esta gravação?", contexto: "Gravações › " + g.titulo, texto: "O áudio, a transcrição e as notas saem da lista. " + LIXEIRA_TEXTO + " Depois disso o áudio some desta máquina.", confirmar: "Apagar", perigo: true }))) return;
  const r = await fetch("/api/gravacoes/" + g.id, { method: "DELETE" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  if (gv.aberta && gv.aberta.id === g.id) gv.aberta = null;
  mostrarGravacoes("lista");
  avisarLixeira(r, () => mostrarGravacoes("lista"));
}

function perguntarSobreGravacao(g) {
  if (!g) return;
  $("nova").click();
  marcarDestino("conversa");
  const campo = $("pedido");
  if (!campo) return;
  campo.value = "Sobre a gravação “" + g.titulo + "” (" + quandoDaGravacao(g) + (g.servico_nome ? ", serviço " + g.servico_nome : "") + ")" +
    (g.resumo ? ", cujo resumo é: " + g.resumo.trim().slice(0, 1500) : (g.notas ? ", com estas notas: " + g.notas.trim() : "")) + ": ";
  campo.focus();
  campo.setSelectionRange(campo.value.length, campo.value.length);
}

